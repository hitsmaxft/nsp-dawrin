"""Construct tiny synthetic encrypted containers; no application data."""
import hashlib
import struct
from content import decrypt
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

HEADER=hashlib.sha256(b'synthetic header').digest()
AREA=hashlib.sha256(b'synthetic key area').digest()[:16]
DATA=hashlib.sha256(b'synthetic section').digest()[:16]
APP=0x0100000000000000


def encrypt(key,mode,data):
    op=Cipher(algorithms.AES(key),mode).encryptor();return op.update(data)+op.finalize()


def pfs(entries,magic=b'PFS0'):
    strings=bytearray();table=bytearray();payload=bytearray();width=24 if magic==b'PFS0' else 64
    for name,data in entries.items():
        table.extend(struct.pack('<QQII',len(payload),len(data),len(strings),0)+bytes(width-24))
        strings.extend(name.encode()+b'\0');payload.extend(data)
    return struct.pack('<4sIII',magic,len(entries),len(strings),0)+table+strings+payload


def romfs(data,name='sample'):
    name=name.encode();dirs=struct.pack('<6I',0xffffffff,0xffffffff,0xffffffff,0,0xffffffff,0)
    files=struct.pack('<IIQQII',0,0xffffffff,0,len(data),0xffffffff,len(name))+name
    data_offset=80+len(dirs)+len(files)
    header=struct.pack('<10Q',80,0,0,80,len(dirs),0,0,80+len(dirs),len(files),data_offset)
    return header+dirs+files+data


def nca(title,kind,parts):
    header=bytearray(0xc00);header[0x200:0x204]=b'NCA3';header[0x205]=kind
    struct.pack_into('<Q',header,0x210,title)
    header[0x300:0x340]=encrypt(AREA,modes.ECB(),bytes(32)+DATA+bytes(16))
    result=bytearray(0xc00)
    for i,(typ,data) in enumerate(parts):
        start=len(result);clear=bytes(0x100)+data;clear+=bytes((-len(clear))%512)
        sh=bytearray(512);sh[2:5]=bytes([1,2,3]) if typ=='pfs' else bytes([0,3,3])
        if typ=='pfs':struct.pack_into('<QQ',sh,0x40,0x100,len(data))
        else:sh[8:12]=b'IVFC';struct.pack_into('<Q',sh,0x90,0x100)
        sh[0x140:0x148]=(7).to_bytes(8,'little');prefix=sh[0x140:0x148][::-1]
        result.extend(encrypt(DATA,modes.CTR(prefix+(start//16).to_bytes(8,'big')),clear))
        struct.pack_into('<II',header,0x240+i*16,start//512,len(result)//512)
        header[0x400+i*512:0x600+i*512]=sh
    struct.pack_into('<Q',header,0x208,len(result))
    result[:0xc00]=b''.join(encrypt(HEADER,modes.XTS(i.to_bytes(16,'big')),header[i*512:(i+1)*512]) for i in range(6))
    return bytes(result)


def cnmt(title,kind,version,records,required=0):
    head=bytearray(0x20);struct.pack_into('<QIBBHHH',head,0,title,version,kind,0,16,len(records),0)
    ext=struct.pack('<QII',APP if kind!=0x80 else APP+0x800,required,0)
    content=bytearray()
    for name,data,typ in records:
        content.extend(hashlib.sha256(data).digest()+bytes.fromhex(name)+len(data).to_bytes(6,'little')+bytes([typ,0]))
    return bytes(head)+ext+content


def package(title=APP,kind=0x80,version=0,payload=b'base content',required=0):
    parts=[('rom',romfs(payload))]
    if kind!=0x82:parts.insert(0,('pfs',pfs({'main':b'synthetic executable','rtld':b'synthetic loader'})))
    code=nca(title,4 if kind==0x82 else 0,parts);name=hashlib.sha256(code).hexdigest()[:32]
    meta=nca(title,1,[('pfs',pfs({'content.cnmt':cnmt(title,kind,version,[(name,code,2 if kind==0x82 else 1)],required)}))])
    return {name+'.nca':code,hashlib.sha256(meta).hexdigest()[:32]+'.cnmt.nca':meta}


def write_keys(path):
    path.write_text('header_key = '+HEADER.hex()+'\nkey_area_key_application_00 = '+AREA.hex()+'\n')
