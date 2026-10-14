"""Build isolated translation jobs from captures and validated shader facts."""
import hashlib
import json
from pathlib import Path
import re
import struct
from nsp_runtime.cache import atomic_write
from nsp_runtime.facts import JsonFactsProvider


def prepare(directory,chain,key=None,variant=None,runtime_facts=None):
    directory=Path(directory);out=directory/'translated'/chain;out.mkdir(parents=True,exist_ok=True)
    for value in (key,variant):
        if value is not None and not re.fullmatch('[0-9a-f]{16}',value):raise ValueError('Invalid shader key')
    if variant and not key:raise ValueError('A variant requires its capture key')
    external=JsonFactsProvider(directory/'shader-facts.json')
    controls=[directory/(key+'.control')] if key else sorted(directory.glob('*.control'))
    jobs=[];reports={};failures={}
    for path in controls:
        identity=variant or path.stem
        try:
            control=path.read_bytes();code=path.with_suffix('.code').read_bytes()
            if len(control)!=0x880 or len(code)<0x80 or code[:4]!=bytes.fromhex('78563412'):
                raise ValueError('Unsupported shader capture layout')
            if hashlib.sha256(control).hexdigest()[:16]!=path.stem:raise ValueError('Capture control hash differs from filename')
            constant,size=struct.unpack_from('<II',control,0x700)
            if not 0x80<=constant<=size==len(code):raise ValueError('Invalid shader code extent')
            kind=(struct.unpack_from('<I',code,0x30)[0]>>10)&15
            row=external.rows.get(path.stem,{})
            stage=(runtime_facts or {}).get('stage',row.get('stage',{1:'vs',5:'ps'}.get(kind)))
            if stage not in ('vs','ps','cs'):raise ValueError(f'Unsupported shader stage: {kind}')
            fact=external.facts_for(path.stem,stage)
            values=dict(fact.values)
            for name,entries in (runtime_facts or {}).get('values',{}).items():
                values[name]={**values.get(name,{}),**entries} if isinstance(entries,dict) else entries
            validate_facts(values,stage)
            code_offset=row.get('code_offset',0x30 if stage!='cs' else None)
            if code_offset is None:raise ValueError('Missing compute code offset metadata')
            if type(code_offset) is not int or not 0<=code_offset<constant or code_offset%8:raise ValueError('Invalid shader code offset')
            dst=out/(identity+'.maxwell');atomic_write(dst,code[code_offset:constant])
            jobs.append(dict(key=identity,source_key=path.stem,stage=stage,code=str(dst),c1=code[constant:size].hex(),debug=False,**values))
            reports[identity]=dict(source='runtime-state' if runtime_facts else fact.source,complete=fact.complete,
                                   source_key=path.stem,code_sha256=hashlib.sha256(code).hexdigest())
        except (OSError,ValueError,KeyError) as error:
            failures[identity]=str(error)
    target=directory/'jobs.json';old=[]
    if key and target.exists():
        old=[j for j in json.loads(target.read_text()) if j['key'] not in {variant or key}
             and Path(j['code']).parent==out]
    atomic_write(target,json.dumps(old+jobs,indent=2))
    facts_path=directory/'facts-report.json'
    previous=json.loads(facts_path.read_text()) if key and facts_path.exists() else {}
    atomic_write(facts_path,json.dumps({**previous,**reports},indent=2))
    atomic_write(directory/'capture-failures.json',json.dumps(failures,indent=2))
    if key and failures:raise ValueError(next(iter(failures.values())))
    return jobs,failures


def prepare_observed(directory, chain):
    """Rebuild observed variants from captures and facts, never from old binaries."""
    directory = Path(directory)
    previous = json.loads((directory/'jobs.json').read_text())
    requests = {}
    for job in previous:
        key, source = job['key'], job['source_key']
        if not all(isinstance(value, str) and re.fullmatch('[0-9a-f]{16}', value)
                   for value in (key, source)):
            raise ValueError('Invalid observed shader identity')
        facts = json.loads((directory/(key+'.facts.json')).read_text())
        identity = json.dumps(dict(capture=source, facts=facts), sort_keys=True,
                              separators=(',', ':'), ensure_ascii=False).encode()
        if hashlib.sha256(identity).hexdigest()[:16] != key:
            raise ValueError('Observed shader facts do not match their variant identity')
        requests[key] = (source, facts)
    if not requests:
        raise ValueError('No observed shader variants are available')
    jobs, failures = [], {}
    for key, (source, facts) in requests.items():
        selected, failed = prepare(directory, chain, source, key, facts)
        jobs.extend(selected)
        failures.update(failed)
    return jobs, failures


def validate_facts(values,stage):
    allowed={'tex','img','attr','fout','local','shared'}
    if set(values)-allowed:raise ValueError('Unknown shader facts field')
    types={'1d','1darray','2d','2darray','2dms','2dmsarray','3d','cube','cubearray','buffer'}
    for table,limit in (('tex',128),('img',32),('attr',32),('fout',8)):
        entries=values.get(table,{})
        if not isinstance(entries,dict):raise ValueError('Invalid shader facts table')
        for slot,value in entries.items():
            if not re.fullmatch(r'\d+',slot) or not 0<=int(slot)<limit:raise ValueError('Shader facts slot exceeds bounds')
            if table in ('attr','fout') and value not in ('float','sint','uint'):raise ValueError('Invalid scalar type')
            if table=='tex' and value not in types:raise ValueError('Invalid texture type')
            if table=='img' and (not isinstance(value,dict) or value.get('type') not in types or not re.fullmatch('[A-Za-z0-9]+',value.get('fmt',''))):raise ValueError('Invalid image facts')
    if stage=='cs':
        local=values.get('local');shared=values.get('shared')
        if not isinstance(local,list) or len(local)!=3 or any(type(n) is not int or not 1<=n<=1024 for n in local) or local[0]*local[1]*local[2]>1024:
            raise ValueError('Missing or invalid compute workgroup metadata')
        if type(shared) is not int or not 0<=shared<=65536:raise ValueError('Missing or invalid compute shared-memory metadata')
