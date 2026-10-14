"""Read a base NSP directly. Resource bytes stay in the original package."""
import argparse
import json
import os
from pathlib import Path
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def decrypt(key,mode,data):
    c=Cipher(algorithms.AES(key),mode).decryptor()
    return c.update(data)+c.finalize()

class Package:
    def __init__(self,path,keys):
        self.path=Path(path).resolve();self.fd=os.open(self.path,os.O_RDONLY)
        self.keys={a.strip():bytes.fromhex(b.strip()) for line in Path(keys).read_text().splitlines()
                   if '=' in line and not line.lstrip().startswith('#') for a,b in [line.split('=',1)]}
        top=self.pfs(lambda o,n:os.pread(self.fd,n,o),0)
        tickets={}
        for name,(off,size) in top.items():
            if name.endswith('.tik'):
                t=os.pread(self.fd,size,off)
                if t[:4]!=b'\x04\x00\x01\x00' or t[0x281]!=0:raise ValueError('Unsupported ticket type')
                tickets[t[0x2a0:0x2b0]]=t[0x180:0x190]
        for name,(off,size) in top.items():
            if not name.endswith('.nca'):continue
            h=os.pread(self.fd,0xc00,off)
            h=b''.join(decrypt(self.keys['header_key'],modes.XTS(i.to_bytes(16,'big')),h[i*512:(i+1)*512]) for i in range(6))
            if h[0x200:0x204]!=b'NCA3':raise ValueError('Only base NCA3 is supported')
            if h[0x205]==0:break
        else:raise ValueError('No Program content in package')
        self.nca_offset=off;self.header=h;self.title_id='%016x'%struct.unpack_from('<Q',h,0x210)[0]
        rev=max(0,max(h[0x206],h[0x220])-1);rid=h[0x230:0x240]
        if any(rid):
            self.key=decrypt(self.keys['titlekek_%02x'%rev],modes.ECB(),tickets[rid])
        else:
            kinds=('application','ocean','system');key=self.keys['key_area_key_%s_%02x'%(kinds[h[0x207]],rev)]
            self.key=decrypt(key,modes.ECB(),h[0x300:0x340])[32:48]
        self.sections=[]
        for i in range(4):
            start,end=struct.unpack_from('<II',h,0x240+i*16)
            if not start:continue
            sh=h[0x400+i*512:0x600+i*512]
            if sh[4] not in (1,3):raise ValueError('Base CTR/plain sections only; updates are not merged')
            sec=dict(offset=start*512,size=(end-start)*512,header=sh,ctr=sh[0x140:0x148][::-1],encrypted=sh[4]==3)
            self.sections.append(sec)
        self.exefs={};self.files={}
        for sec in self.sections:
            sh=sec['header'];read=lambda o,n,s=sec:self.read(s,o,n)
            if sh[2:4]==bytes([1,2]):
                base=sec['offset']+struct.unpack_from('<Q',sh,0x40)[0]
                entries=self.pfs(read,base)
                if 'main' in entries and 'rtld' in entries:
                    self.exefs=entries;self.exe_section=sec
            elif sh[2:4]==bytes([0,3]):
                assert sh[8:12]==b'IVFC'
                base=sec['offset']+struct.unpack_from('<Q',sh,0x90)[0]
                rh=struct.unpack('<10Q',read(base,80));assert rh[0]==80
                dirs=read(base+rh[3],rh[4]);files=read(base+rh[7],rh[8]);self.rom_section=sec
                seen=set()
                def walk(at,parent):
                    if at in seen:raise ValueError('Cyclic RomFS directories')
                    seen.add(at)
                    _,sib,child,first,_,nl=struct.unpack_from('<6I',dirs,at)
                    name=dirs[at+24:at+24+nl].decode();path=parent+'/'+name if parent and name else parent or name
                    fi=first
                    while fi!=0xffffffff:
                        _,nxt,fo,sz,_,n=struct.unpack_from('<IIQQII',files,fi)
                        fn=files[fi+32:fi+32+n].decode();full=(path+'/'+fn).lstrip('/')
                        if '..' in Path(full).parts:raise ValueError('Unsafe resource path')
                        self.files[full]=(base+rh[9]+fo,sz);fi=nxt
                    if child!=0xffffffff:walk(child,path)
                    if sib!=0xffffffff:walk(sib,parent)
                walk(0,'')
        if not self.exefs or not self.files:raise ValueError('Executable or RomFS missing')
    @staticmethod
    def pfs(read,base):
        magic,n,ss,_=struct.unpack('<4sIII',read(base,16));assert magic==b'PFS0'
        assert n<100000 and ss<16777216
        table=read(base+16,n*24);strings=read(base+16+n*24,ss);entries={}
        for i in range(n):
            off,size,no,_=struct.unpack_from('<QQII',table,i*24);name=strings[no:].split(b'\0')[0].decode()
            if '/' in name or '..' in name:raise ValueError('Unsafe archive name')
            entries[name]=(base+16+n*24+ss+off,size)
        return entries
    def read(self,section,offset,size):
        if offset<section['offset'] or offset+size>section['offset']+section['size']:raise ValueError('Section bounds')
        start=offset&~15;end=(offset+size+15)&~15
        raw=os.pread(self.fd,end-start,self.nca_offset+start)
        if len(raw)!=end-start:raise IOError('Short package read')
        if section['encrypted']:raw=decrypt(self.key,modes.CTR(section['ctr']+(start//16).to_bytes(8,'big')),raw)
        return raw[offset-start:offset-start+size]
    def resource(self,name):
        return self.read_resource(name)
    def iter_resources(self):
        from nsp_runtime.interfaces import Resource
        return (Resource(name,size) for name,(_,size) in self.files.items())
    def read_resource(self,path,offset=0,length=None):
        base,size=self.files[path]
        if offset<0 or (length is not None and length<0):raise ValueError('Negative resource range')
        if offset>=size:return b''
        length=size-offset if length is None else min(length,size-offset)
        return self.read(self.rom_section,base+offset,length) if length else b''
    def close(self):os.close(self.fd)
    def prepare(self,out):
        out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
        ex=out/'ExeFS';ex.mkdir(exist_ok=True)
        for name,(off,size) in self.exefs.items():
            (ex/name).write_bytes(self.read(self.exe_section,off,size))
        vfs=out/'vfs';vfs.mkdir(exist_ok=True)
        # Index-only sparse entries allow normal stat/readdir without unpacking data.
        for name,(off,size) in self.files.items():
            p=vfs/name;p.parent.mkdir(parents=True,exist_ok=True)
            if not p.exists():
                fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o400);os.ftruncate(fd,size);os.close(fd)
            elif p.stat().st_size!=size:raise ValueError('Existing VFS index does not match package')
        secret=out/'package-key.bin'
        fd=os.open(secret,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);os.fchmod(fd,0o600);os.write(fd,self.key);os.close(fd)
        sec=self.rom_section
        manifest=dict(version=1,package=str(self.path),package_bytes=self.path.stat().st_size,
                      nca_offset=self.nca_offset,title_id=self.title_id,root=str(vfs),
                      key_file=str(secret),ctr_prefix=sec['ctr'].hex(),encrypted=sec['encrypted'],files=self.files)
        (out/'package-index.json').write_text(json.dumps(manifest,ensure_ascii=False))
        print(json.dumps(dict(title_id=self.title_id,resources=len(self.files),executable_bytes=sum(s for _,s in self.exefs.values()),resource_bytes=sum(s for _,s in self.files.values()),romfs_extracted=False),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package');p.add_argument('keys');p.add_argument('output');a=p.parse_args()
    game=Package(a.package,a.keys)
    try:game.prepare(a.output)
    finally:game.close()
