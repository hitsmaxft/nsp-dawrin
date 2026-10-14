"""Bounded package, metadata and virtual-section readers for application content.

Container and BKTR layouts were checked against SciresM's hactool (ISC).
See docs/DEPENDENCIES.md for provenance. No platform data is embedded here.
"""
from bisect import bisect_right
from dataclasses import dataclass
import json
import os
from pathlib import Path
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class ContentError(ValueError):
    pass


def decrypt(key, mode, data):
    operation = Cipher(algorithms.AES(key), mode).decryptor()
    return operation.update(data) + operation.finalize()


def bounds(offset, size, total):
    if offset < 0 or size < 0 or offset > total or size > total-offset:
        raise ContentError('Content range exceeds its container')


def read_exact(read, offset, size):
    data = read(offset, size)
    if len(data) != size:
        raise ContentError('Truncated content')
    return data


def archive(read, base, size, magic=b'PFS0'):
    """Read a PFS0/HFS0 index, with offsets relative to the supplied reader."""
    bounds(base, size, 2**63-1)
    header = read_exact(read, base, 16)
    actual, count, strings_size, _ = struct.unpack('<4sIII', header)
    width = 24 if magic == b'PFS0' else 64
    if actual != magic or count > 100000 or strings_size > 16*1024*1024:
        raise ContentError('Invalid archive header')
    data_start = 16 + count*width + strings_size
    bounds(0, data_start, size)
    table = read_exact(read, base+16, count*width)
    strings = read_exact(read, base+16+count*width, strings_size)
    result = {}
    for i in range(count):
        offset, length, name_offset = struct.unpack_from('<QQI', table, i*width)
        if name_offset >= len(strings) or b'\0' not in strings[name_offset:]:
            raise ContentError('Invalid archive name')
        name = strings[name_offset:].split(b'\0', 1)[0].decode('utf-8')
        if not name or '/' in name or '\\' in name or name in ('.', '..') or name in result:
            raise ContentError('Unsafe or duplicate archive name')
        bounds(data_start+offset, length, size)
        result[name] = (base+data_start+offset, length)
    return result


class KeyStore:
    def __init__(self, path):
        self.values = {}
        for line in Path(path).read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                try: self.values[name.strip()] = bytes.fromhex(value.strip())
                except ValueError: raise ContentError('Invalid key file encoding') from None

    def get(self, name, size=16):
        value = self.values.get(name)
        if value is None:
            raise ContentError(f'Missing local key: {name}')
        if len(value) != size:
            raise ContentError(f'Invalid key length: {name}')
        return value


class Container:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.fd = os.open(self.path, os.O_RDONLY)
        self.size = os.fstat(self.fd).st_size
        try:
            if self.read(0, 4) == b'PFS0':
                self.entries = archive(self.read, 0, self.size)
                self.format = 'nsp'
            elif self.size >= 0x200 and self.read(0x100, 4) == b'HEAD':
                offset = struct.unpack('<Q', self.read(0x130, 8))[0]
                bounds(offset, 16, self.size)
                partitions = archive(self.read, offset, self.size-offset, b'HFS0')
                if 'secure' not in partitions: raise ContentError('XCI secure partition is missing')
                start, size = partitions['secure']
                self.entries = archive(self.read, start, size, b'HFS0')
                self.format = 'xci'
            else:
                raise ContentError('Expected an uncompressed NSP or XCI container')
            self.tickets = {}
            for name, (offset, size) in self.entries.items():
                if name.endswith('.tik'):
                    if size < 0x2b0: raise ContentError('Truncated ticket')
                    ticket = self.read(offset, 0x2b0)
                    if ticket[:4] != b'\x04\0\x01\0' or ticket[0x281] != 0:
                        raise ContentError('Personalized or unsupported ticket')
                    self.tickets[ticket[0x2a0:0x2b0]] = ticket[0x180:0x190]
        except BaseException:
            self.close()
            raise

    def read(self, offset, size):
        bounds(offset, size, self.size)
        return read_exact(lambda o,n: os.pread(self.fd,n,o), offset, size)

    def close(self):
        if self.fd >= 0: os.close(self.fd); self.fd = -1


@dataclass(frozen=True)
class Span:
    start: int
    size: int
    section: object
    offset: int
    prefix: bytes


class Section:
    def __init__(self, nca, index, start, size, header):
        self.nca, self.index, self.start, self.size, self.header = nca,index,start,size,header
        self.crypto = header[4]
        if self.crypto not in (1,3,4):
            raise ContentError(f'Unsupported section encryption: {self.crypto}')
        # Sparse and compressed sections need distinct storage adapters.
        if any(header[0x148:0x190]) or any(header[0x198:0x1c0]):
            raise ContentError('Sparse or compressed section storage is not supported')
        self.prefix = bytes(header[0x140:0x148][::-1])
        self.spans = [Span(0,size,self,0,self.prefix)]
        self.starts = [0]
        self.virtual_size = size

    def physical(self, offset, size, prefix=None):
        bounds(offset, size, self.size)
        if not size: return b''
        absolute = self.start+offset
        if self.crypto == 1: return self.nca.read(absolute,size)
        aligned = absolute & ~15
        stop = (absolute+size+15) & ~15
        raw = self.nca.read(aligned,stop-aligned)
        iv = (prefix or self.prefix)+(aligned//16).to_bytes(8,'big')
        return decrypt(self.nca.key,modes.CTR(iv),raw)[absolute-aligned:absolute-aligned+size]

    def read(self, offset, size):
        bounds(offset,size,self.virtual_size)
        result = bytearray()
        while size:
            span = self.spans[bisect_right(self.starts,offset)-1]
            count = min(size,span.start+span.size-offset)
            if count <= 0: raise ContentError('Gap in virtual section')
            result.extend(span.section.physical(span.offset+offset-span.start,count,span.prefix))
            offset += count; size -= count
        return bytes(result)

    def patch(self, base):
        """Flatten BKTR relocations and crypto subsections into bounded spans."""
        if self.crypto != 4: return
        if base is None: raise ContentError('Patch requires the matching base section')
        descriptors = []
        for at in (0x100,0x120):
            offset,size,magic,version,entries,_ = struct.unpack_from('<QQ4sIII',self.header,at)
            if magic != b'BKTR' or version != 1: raise ContentError('Unsupported BKTR tree')
            bounds(offset,size,self.size)
            if size > 64*1024*1024: raise ContentError('BKTR tree exceeds metadata limit')
            descriptors.append((offset,size,entries))
        (ro,rs,rn),(so,ss,sn) = descriptors
        if ro+rs != so or so+ss != self.size: raise ContentError('Invalid BKTR tree layout')
        def tree(offset,size,count,width,fmt):
            data = self.physical(offset,size)
            if len(data)<0x4000: raise ContentError('Truncated BKTR root')
            _,buckets,total = struct.unpack_from('<IIQ',data)
            if not 0 < buckets <= 0x3ff0//8 or (buckets+1)*0x4000 > len(data):
                raise ContentError('Unsupported BKTR tree depth')
            rows=[]
            for i in range(buckets):
                at=(i+1)*0x4000
                _,n,end=struct.unpack_from('<IIQ',data,at)
                if not 0<n<=0x3ff0//width: raise ContentError('Invalid BKTR bucket')
                bucket=[struct.unpack_from(fmt,data,at+16+j*width) for j in range(n)]
                if bucket[0][0] != struct.unpack_from('<Q',data,16+i*8)[0] or bucket[-1][0]>=end:
                    raise ContentError('Invalid BKTR bucket bounds')
                rows.extend(bucket)
            if len(rows)!=count or rows[0][0]!=0 or any(a[0]>=b[0] for a,b in zip(rows,rows[1:])) or rows[-1][0]>=total:
                raise ContentError('Invalid BKTR entry ordering')
            return rows,total
        relocations,total=tree(ro,rs,rn,20,'<QQI')
        subsections,physical_end=tree(so,ss,sn,16,'<QII')
        if physical_end!=so or subsections[-1][0]>=ro: raise ContentError('Invalid BKTR subsection extent')
        sub_starts=[r[0] for r in subsections]+[ro]
        spans=[]
        for i,(virtual,physical,is_patch) in enumerate(relocations):
            end=relocations[i+1][0] if i+1<len(relocations) else total
            if is_patch not in (0,1): raise ContentError('Invalid BKTR source')
            left=end-virtual
            if is_patch:
                bounds(physical,left,ro)
                while left:
                    idx=bisect_right(sub_starts,physical)-1
                    count=min(left,sub_starts[idx+1]-physical)
                    if count<=0: raise ContentError('Invalid BKTR crypto range')
                    prefix=self.prefix[:4]+subsections[idx][2].to_bytes(4,'big')
                    spans.append(Span(virtual,count,self,physical,prefix))
                    virtual+=count;physical+=count;left-=count
            else:
                bounds(physical,left,base.virtual_size)
                while left:
                    source=base.spans[bisect_right(base.starts,physical)-1]
                    count=min(left,source.start+source.size-physical)
                    spans.append(Span(virtual,count,source.section,source.offset+physical-source.start,source.prefix))
                    virtual+=count;physical+=count;left-=count
        self.spans=spans;self.starts=[s.start for s in spans];self.virtual_size=total

    def pfs(self):
        offset,size=struct.unpack_from('<QQ',self.header,0x40)
        bounds(offset,size,self.virtual_size)
        return archive(self.read,offset,size)

    def romfs(self):
        if self.header[8:12]!=b'IVFC': raise ContentError('Unsupported RomFS hash layout')
        base=struct.unpack_from('<Q',self.header,0x90)[0]
        values=struct.unpack('<10Q',self.read(base,80))
        if values[0]!=80: raise ContentError('Invalid RomFS header')
        _,_,_,do,ds,_,_,fo,fs,data_offset=values
        if ds+fs>64*1024*1024: raise ContentError('RomFS metadata exceeds limit')
        dirs=self.read(base+do,ds);files=self.read(base+fo,fs)
        result={};seen=set();seen_files=set();stack=[(0,'')]
        while stack:
            at,parent=stack.pop()
            if at in seen: raise ContentError('Cyclic RomFS directory')
            seen.add(at);bounds(at,24,len(dirs))
            _,sib,child,first,_,nl=struct.unpack_from('<6I',dirs,at)
            bounds(at+24,nl,len(dirs));name=dirs[at+24:at+24+nl].decode()
            if '/' in name or '\\' in name or name in ('.','..'): raise ContentError('Unsafe directory name')
            path=f'{parent}/{name}'.strip('/')
            fi=first
            while fi!=0xffffffff:
                if fi in seen_files: raise ContentError('Cyclic RomFS file list')
                seen_files.add(fi);bounds(fi,32,len(files))
                _,nxt,off,size,_,length=struct.unpack_from('<IIQQII',files,fi)
                bounds(fi+32,length,len(files));name=files[fi+32:fi+32+length].decode()
                if not name or '/' in name or '\\' in name or name in ('.','..'): raise ContentError('Unsafe resource name')
                full=f'{path}/{name}'.lstrip('/')
                if full in result: raise ContentError('Duplicate RomFS path')
                bounds(base+data_offset+off,size,self.virtual_size)
                result[full]=(base+data_offset+off,size);fi=nxt
            if child!=0xffffffff:stack.append((child,path))
            if sib!=0xffffffff:stack.append((sib,parent))
        return result


class Nca:
    def __init__(self, container, name, keys):
        self.container=container;self.name=name
        self.offset,self.size=container.entries[name]
        encrypted=self.read(0,0xc00)
        header_key=keys.get('header_key',32)
        self.header=b''.join(decrypt(header_key,modes.XTS(i.to_bytes(16,'big')),encrypted[i*512:(i+1)*512]) for i in range(6))
        h=self.header
        if h[0x200:0x204]!=b'NCA3': raise ContentError('Unsupported NCA version or header key')
        if struct.unpack_from('<Q',h,0x208)[0]!=self.size: raise ContentError('NCA size mismatch')
        self.kind=h[0x205];self.title_id=struct.unpack_from('<Q',h,0x210)[0]
        revision=max(0,max(h[0x206],h[0x220])-1);rights=h[0x230:0x240]
        if any(rights):
            ticket=container.tickets.get(rights)
            if ticket is None: raise ContentError('Required common ticket is missing')
            self.key=decrypt(keys.get(f'titlekek_{revision:02x}'),modes.ECB(),ticket)
        else:
            if h[0x207]>2: raise ContentError('Unknown NCA key area')
            kind=('application','ocean','system')[h[0x207]]
            self.key=decrypt(keys.get(f'key_area_key_{kind}_{revision:02x}'),modes.ECB(),h[0x300:0x340])[32:48]
        self.sections=[]
        for i in range(4):
            start,end=struct.unpack_from('<II',h,0x240+i*16)
            if not start:continue
            bounds(start*512,(end-start)*512,self.size)
            self.sections.append(Section(self,i,start*512,(end-start)*512,h[0x400+i*512:0x600+i*512]))

    def read(self, offset, size):
        bounds(offset,size,self.size)
        return self.container.read(self.offset+offset,size)


@dataclass
class Metadata:
    title_id: int
    version: int
    kind: int
    application_id: int
    required_version: int
    records: list
    container: object


def metadata(data, container=None):
    if len(data)<0x20:raise ContentError('Truncated content metadata')
    title,version,kind,_,ext_size,count,meta_count=struct.unpack_from('<QIBBHHH',data)
    bounds(0x20,ext_size+count*0x38+meta_count*0x10,len(data))
    if kind not in (0x80,0x81,0x82): raise ContentError(f'Unsupported content metadata type: {kind:#x}')
    if ext_size<16:raise ContentError('Truncated extended content metadata')
    app=title if kind==0x80 else struct.unpack_from('<Q',data,0x20)[0]
    required=struct.unpack_from('<I',data,0x28)[0] if kind==0x82 else 0
    records=[]
    for i in range(count):
        at=0x20+ext_size+i*0x38
        records.append(dict(id=data[at+32:at+48].hex(),size=int.from_bytes(data[at+48:at+54],'little'),
                            type=data[at+54],index=data[at+55]))
    return Metadata(title,version,kind,app,required,records,container)


class ContentSet:
    """Select a base, newest supplied update and compatible add-on content."""
    def __init__(self, paths, keys, application_id=None):
        self.containers=[];self.ncas={};self.mounts=[]
        keys=keys if isinstance(keys,KeyStore) else KeyStore(keys)
        try:
            for path in paths:self.containers.append(Container(path))
            rows=[]
            for container in self.containers:
                for name in container.entries:
                    if not name.endswith('.cnmt.nca'):continue
                    nca=self._nca(container,name,keys)
                    for section in nca.sections:
                        if section.header[2:4]!=bytes([1,2]):continue
                        for filename,(offset,size) in section.pfs().items():
                            if filename.endswith('.cnmt'):
                                if size>16*1024*1024:raise ContentError('Content metadata exceeds limit')
                                rows.append(metadata(section.read(offset,size),container))
            bases=[row for row in rows if row.kind==0x80 and (application_id is None or row.title_id==application_id)]
            if len(bases)!=1:raise ContentError('Select exactly one base application using --application-id')
            self.base=bases[0];self.title_id=f'{self.base.title_id:016x}'
            if any(row.application_id!=self.base.title_id for row in rows):
                # XCI compilation containers may contain several base applications.
                if application_id is None:raise ContentError('Supplied content belongs to different applications')
            self.rows=[row for row in rows if row.application_id==self.base.title_id]
            if any(not any(row.container is container for row in self.rows) for container in self.containers):
                raise ContentError('An explicitly supplied package does not belong to the selected application')
            updates=sorted((row for row in self.rows if row.kind==0x81),key=lambda r:r.version)
            if len({r.version for r in updates})!=len(updates):raise ContentError('Ambiguous duplicate update version')
            self.update=updates[-1] if updates else None
            self.version=self.update.version if self.update else self.base.version
            self.save_sizes=None
            control_row=self.update if self.update and any(r['type']==3 for r in self.update.records) else self.base
            if any(r['type']==3 for r in control_row.records):
                control=self._content(control_row,3,keys)
                for section in control.sections:
                    if section.header[2:4]!=bytes([0,3]):continue
                    entries=section.romfs()
                    if 'control.nacp' in entries:
                        offset,size=entries['control.nacp']
                        if size<0x3090:raise ContentError('Truncated application control property')
                        data,journal=struct.unpack('<QQ',section.read(offset+0x3080,16))
                        if data>2**63-1 or journal>2**63-1:raise ContentError('Invalid save allocation')
                        self.save_sizes=dict(data=data,journal=journal)
            program=self._content(self.base,1,keys)
            original_rom=next((s for s in program.sections if s.header[2:4]==bytes([0,3])),None)
            active=program
            if self.update:
                active=self._content(self.update,1,keys)
                for section in active.sections:
                    if section.crypto==4:section.patch(original_rom)
            self.exefs={};self.exe_section=None
            for section in active.sections:
                if section.header[2:4]==bytes([1,2]):
                    entries=section.pfs()
                    if 'main' in entries:
                        self.exefs=entries;self.exe_section=section
            rom=next((s for s in active.sections if s.header[2:4]==bytes([0,3])),original_rom)
            if not self.exefs or rom is None:raise ContentError('Executable or RomFS is missing')
            self.files=rom.romfs();self.rom_section=rom
            self.mounts.append(dict(kind='base',id=self.title_id,section=rom,files=self.files))
            addons={}
            for row in sorted((r for r in self.rows if r.kind==0x82),key=lambda r:r.version):
                if row.required_version>self.version:raise ContentError('DLC requires a newer application update')
                index=row.title_id-(self.base.title_id+0x1000)
                if not 0<=index<=0xffff:raise ContentError('DLC content index is outside the application range')
                if index in addons and addons[index].version==row.version:raise ContentError('Ambiguous duplicate DLC version')
                addons[index]=row
            for index,row in sorted(addons.items()):
                data=self._content(row,2,keys)
                section=next((s for s in data.sections if s.header[2:4]==bytes([0,3])),None)
                if section is None:raise ContentError('DLC data has no RomFS section')
                if section.crypto==4:raise ContentError('DLC patch sections need a matching DLC base')
                self.mounts.append(dict(kind='dlc',id=f'{row.title_id:016x}',index=index,version=row.version,
                                        section=section,files=section.romfs()))
        except BaseException:
            self.close();raise

    def _nca(self,container,name,keys):
        identity=(container.path,name)
        if identity not in self.ncas:self.ncas[identity]=Nca(container,name,keys)
        return self.ncas[identity]

    def _content(self,row,kind,keys):
        records=[r for r in row.records if r['type']==kind]
        if len(records)!=1 or records[0]['index']!=0:
            raise ContentError('Expected one primary content record; multi-program content needs an adapter')
        record=records[0];name=record['id']+'.nca'
        if name not in row.container.entries:raise ContentError('Referenced content archive is missing')
        nca=self._nca(row.container,name,keys)
        if nca.size!=record['size']:raise ContentError('Metadata content size mismatch')
        return nca

    def iter_resources(self):
        from nsp_runtime.interfaces import Resource
        return (Resource(name,size) for name,(_,size) in self.files.items())

    def read_resource(self,path,offset=0,length=None):
        start,size=self.files[path]
        if offset<0 or (length is not None and length<0):raise ContentError('Negative resource range')
        if offset>=size:return b''
        count=size-offset if length is None else min(length,size-offset)
        return self.rom_section.read(start+offset,count)

    resource=read_resource

    def close(self):
        for container in self.containers:container.close()

    def describe(self):
        return dict(title_id=self.title_id,application_version=self.version,update=self.update is not None,
                    formats=[c.format for c in self.containers],save_sizes=self.save_sizes,
                    dlc=[dict(id=m['id'],index=m['index'],version=m['version']) for m in self.mounts[1:]])

    def prepare(self,output):
        from nsp_runtime.cache import atomic_write
        output=Path(output).resolve()
        if output.is_relative_to(Path(__file__).resolve().parents[1]):raise ContentError('Runtime data must stay outside the checkout')
        output.mkdir(parents=True,exist_ok=True)
        ex=output/'ExeFS';ex.mkdir(exist_ok=True)
        for name,(offset,size) in self.exefs.items():
            atomic_write(ex/name,self.exe_section.read(offset,size))
        sources=[];source_ids={};mounts=[]
        for mount in self.mounts:
            root=output/'vfs' if mount['kind']=='base' else output/'dlc'/mount['id']/'vfs'
            root.mkdir(parents=True,exist_ok=True)
            names={}
            for name,(_,size) in mount['files'].items():
                path=root/name;relative=Path(name)
                for i in range(1,len(relative.parts)+1):
                    component='/'.join(relative.parts[:i]);folded=component.casefold()
                    if folded in names and names[folded]!=component:raise ContentError('Case-colliding resource paths require a case-sensitive cache volume')
                    names[folded]=component
                path.parent.mkdir(parents=True,exist_ok=True)
                if path.is_symlink():raise ContentError('Resource index contains a symbolic link')
                if not path.exists():
                    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o400)
                    try:os.ftruncate(fd,size)
                    finally:os.close(fd)
                elif path.stat().st_size!=size:raise ContentError('Existing resource index differs; use a new cache directory')
            segments=[]
            for span in mount['section'].spans:
                section=span.section;nca=section.nca;container=nca.container
                identity=(container.path,nca.offset,span.prefix)
                if identity not in source_ids:
                    idx=len(sources);source_ids[identity]=idx
                    keyfile=output/'keys'/f'{idx}.bin';atomic_write(keyfile,nca.key)
                    sources.append(dict(package=str(container.path),package_bytes=container.size,
                                        nca_offset=nca.offset,key_file=str(keyfile),ctr_prefix=span.prefix.hex(),encrypted=section.crypto!=1))
                segments.append(dict(start=span.start,size=span.size,source=source_ids[identity],offset=section.start+span.offset))
            mounts.append(dict(kind=mount['kind'],id=mount['id'],index=mount.get('index',0),root=str(root),
                               files=mount['files'],segments=segments))
        manifest=dict(version=2,**self.describe(),sources=sources,mounts=mounts)
        atomic_write(output/'package-index.json',json.dumps(manifest,indent=2))
        return manifest
