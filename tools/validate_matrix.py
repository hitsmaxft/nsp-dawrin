"""Run bounded application checks and group failures by shared runtime interface."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from compatibility import classify,group
from nsp_runtime.cache import atomic_write
from smoke import run
from service_catalog import catalog

ROOT=Path(__file__).resolve().parents[1]


def cases_from(path):
    data=json.loads(Path(path).read_text());cases=data.get('cases')
    if not isinstance(cases,list) or not 1<=len(cases)<=128:raise ValueError('Expected 1 to 128 cases')
    ids=set()
    for case in cases:
        identity=case.get('id','')
        if not re.fullmatch('[A-Za-z0-9_-]{1,64}',identity) or identity in ids:raise ValueError('Invalid or duplicate case ID')
        ids.add(identity)
        if not isinstance(case.get('cache'),str):raise ValueError('Case cache path is required')
        timeout=case.get('timeout',90)
        if type(timeout) not in (int,float) or not 1<=timeout<=1800:raise ValueError('Invalid case timeout')
    return cases


def validate(cases,output,runner=run):
    if catalog()['conflicts']:raise ValueError('Conflicting host service registrations; run service_catalog.py --check')
    output=Path(output).expanduser().resolve()
    if output.is_relative_to(ROOT):raise ValueError('Validation data must stay outside the checkout')
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    results=[];started=time.monotonic()
    for case in cases:
        target=output/case['id'];target.mkdir(mode=0o700,exist_ok=True)
        try:
            result=runner(Path(case['cache']).expanduser(),timeout=case.get('timeout',90),output=target)
            log=(target/'runtime.log').read_text(errors='replace')
        except (OSError,ValueError,RuntimeError) as error:
            result=dict(outcome='preflight_failed');log=str(error)
            atomic_write(target/'failure.txt',log+'\n')
        counters={k:v for k,v in result.get('last_status',{}).items()
                  if k in ('frames','shader_loads','shader_failures','package_reads','package_bytes') and type(v) is int}
        row=dict(id=case['id'],outcome=result['outcome'],classification=classify(result,log),
                 seconds=result.get('seconds',0),counters=counters)
        results.append(row);print(json.dumps(row),flush=True)
        summary=dict(schema_version=1,complete=len(results)==len(cases),results=results,groups=group(results),
                     seconds=round(time.monotonic()-started,2))
        atomic_write(output/'matrix.json',json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();summary=validate(cases_from(args.manifest),args.output)
    raise SystemExit(bool(summary['groups']))
