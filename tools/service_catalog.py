"""Inspect SDK bindings and reject conflicting service registrations before launch."""
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def catalog(root=ROOT):
    bindings={};conflicts=[]
    for path in sorted((root/'src').rglob('*')):
        if path.suffix not in ('.c','.m') or 'third_party' in path.parts:continue
        text=path.read_text()
        for match in re.finditer(r'HLE_FORCE\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,\s*[^,]+,\s*(\w+)',text):
            symbol,reason,handler=match.groups()
            row=dict(symbol=symbol,handler=handler,module=str(path.relative_to(root)),reason=reason)
            if symbol in bindings:conflicts.append(dict(symbol=symbol,modules=[bindings[symbol]['module'],row['module']]))
            else:bindings[symbol]=row
        for match in re.finditer(r'HLE_GUEST_ALIAS\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]*)"',text):
            symbol,target,reason=match.groups()
            row=dict(symbol=symbol,handler='guest:'+target,module=str(path.relative_to(root)),reason=reason)
            if symbol in bindings:conflicts.append(dict(symbol=symbol,modules=[bindings[symbol]['module'],row['module']]))
            else:bindings[symbol]=row
    return dict(bindings=list(bindings.values()),conflicts=conflicts)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    data=catalog()
    print(json.dumps(dict(bindings=len(data['bindings']),conflicts=data['conflicts']) if args.check else data,indent=2))
    raise SystemExit(bool(data['conflicts']))
