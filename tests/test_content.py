import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from content import ContentSet,ContentError,Container,Section,archive,metadata
from content_fixtures import APP,DATA,package,pfs,write_keys,encrypt
from cryptography.hazmat.primitives.ciphers import modes


class ContentTests(unittest.TestCase):
    def test_nsp_xci_update_dlc_selection_and_prepare(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);keys=root/'local.keys';write_keys(keys)
            base=root/'base.nsp';base.write_bytes(pfs(package()))
            update=root/'update.nsp';update.write_bytes(pfs(package(APP+0x800,0x81,2,b'updated content')))
            dlc=root/'addon.nsp';dlc.write_bytes(pfs(package(APP+0x1001,0x82,0,b'add-on content',2)))
            with self.assertRaisesRegex(ContentError,'newer'):ContentSet([base,dlc],keys)
            game=ContentSet([base,update,dlc],keys)
            try:
                self.assertEqual(game.read_resource('sample'),b'updated content')
                self.assertEqual(game.describe()['dlc'][0]['index'],1)
                index=game.prepare(root/'cache')
                self.assertEqual(index['version'],2);self.assertEqual(len(index['mounts']),2)
                self.assertEqual((root/'cache/ExeFS/main').read_bytes(),b'synthetic executable')
                self.assertEqual(os.stat(index['sources'][0]['key_file']).st_mode&0o777,0o600)
                native=Path(__file__).resolve().parents[2]/'work/bin/test-package-reader'
                if native.exists():
                    for mount,expected in zip(index['mounts'],(b'updated content',b'add-on content')):
                        env=dict(os.environ,DM_PACKAGE_INDEX=str(root/'cache/package-index.json'))
                        actual=subprocess.check_output([str(native),str(Path(mount['root'])/'sample'),'2','100'],env=env)
                        self.assertEqual(actual,expected[2:])
            finally:game.close()
            secure=pfs(package(),b'HFS0');partition=pfs({'secure':secure},b'HFS0')
            header=bytearray(0x200);header[0x100:0x104]=b'HEAD';struct.pack_into('<Q',header,0x130,0x200)
            xci=root/'base.xci';xci.write_bytes(header+partition)
            game=ContentSet([xci],keys)
            try:self.assertEqual(game.read_resource('sample'),b'base content')
            finally:game.close()

    def test_archive_bounds_cycles_and_metadata_rejection(self):
        data=pfs({'sample':b'abc'})
        with self.assertRaises(ContentError):archive(lambda o,n:data[o:o+n],0,len(data)-1)
        with self.assertRaises(ContentError):metadata(bytes(16))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);keys=root/'local.keys';write_keys(keys)
            base=root/'base.nsp';base.write_bytes(pfs(package()))
            wrong=root/'wrong.nsp';wrong.write_bytes(pfs(package(APP+0x2000)))
            with self.assertRaises(ContentError):ContentSet([base,wrong],keys)
            keys.write_text('')
            with self.assertRaisesRegex(ContentError,'Missing local key'):ContentSet([base],keys)

    def test_bktr_crosses_base_patch_and_counter_ranges(self):
        class Nca:
            key=DATA
            def __init__(self,data):self.data=data
            def read(self,o,n):return self.data[o:o+n]
        base_header=bytearray(512);base_header[4]=1
        base=Section(Nca(b'abcdefghijklmnop'),0,0,16,base_header)
        ro,so,total=0x200,0x8200,0x10200
        reloc=bytearray(0x8000);struct.pack_into('<IIQ',reloc,0,0,1,16);struct.pack_into('<Q',reloc,16,0)
        struct.pack_into('<IIQ',reloc,0x4000,0,3,16)
        for i,row in enumerate(((0,0,0),(4,12,1),(12,12,0))):struct.pack_into('<QQI',reloc,0x4010+i*20,*row)
        subs=bytearray(0x8000);struct.pack_into('<IIQ',subs,0,0,1,so);struct.pack_into('<Q',subs,16,0)
        struct.pack_into('<IIQ',subs,0x4000,0,2,so)
        struct.pack_into('<QII',subs,0x4010,0,0,10);struct.pack_into('<QII',subs,0x4020,16,0,11)
        header=bytearray(512);header[4]=4;header[0x140:0x148]=(7).to_bytes(8,'little')
        struct.pack_into('<QQ4sIII',header,0x100,ro,len(reloc),b'BKTR',1,3,0)
        struct.pack_into('<QQ4sIII',header,0x120,so,len(subs),b'BKTR',1,2,0)
        prefix=bytes(header[0x140:0x148][::-1]);clear=bytearray(total);clear[12:20]=b'PATCHED!';clear[ro:so]=reloc;clear[so:]=subs
        raw=bytearray(encrypt(DATA,modes.CTR(prefix+bytes(8)),bytes(clear)))
        raw[:16]=encrypt(DATA,modes.CTR(prefix[:4]+(10).to_bytes(4,'big')+bytes(8)),bytes(clear[:16]))
        raw[16:ro]=encrypt(DATA,modes.CTR(prefix[:4]+(11).to_bytes(4,'big')+(1).to_bytes(8,'big')),bytes(clear[16:ro]))
        patch=Section(Nca(raw),0,0,total,header);patch.patch(base)
        self.assertEqual(patch.read(0,16),b'abcdPATCHED!mnop')
        self.assertEqual(patch.read(3,11),b'dPATCHED!mn')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);key=root/'key.bin';key.write_bytes(DATA)
            source_ids={};sources=[];segments=[]
            for span in patch.spans:
                identity=(id(span.section),span.prefix)
                if identity not in source_ids:
                    index=len(sources);source_ids[identity]=index;path=root/f'{index}.bin';path.write_bytes(span.section.nca.data)
                    sources.append(dict(package=str(path),package_bytes=path.stat().st_size,nca_offset=0,
                        key_file=str(key),ctr_prefix=span.prefix.hex(),encrypted=span.section.crypto!=1))
                segments.append(dict(start=span.start,size=span.size,offset=span.offset,source=source_ids[identity]))
            vfs=root/'vfs';vfs.mkdir();(vfs/'sample').write_bytes(bytes(16))
            manifest=root/'index.json';manifest.write_text(json.dumps(dict(version=2,sources=sources,
                mounts=[dict(kind='base',root=str(vfs),files={'sample':[0,16]},segments=segments)])))
            native=Path(__file__).resolve().parents[2]/'work/bin/test-package-reader'
            if native.exists():
                actual=subprocess.check_output([str(native),str(vfs/'sample'),'3','11'],env=dict(os.environ,DM_PACKAGE_INDEX=str(manifest)))
                self.assertEqual(actual,b'dPATCHED!mn')
        with self.assertRaises(ContentError):patch.read(15,2)


if __name__=='__main__':unittest.main()
