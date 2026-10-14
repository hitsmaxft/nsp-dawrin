"""Prepare and launch an external base package with resources read in place."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from content import ContentSet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--keys', required=True, type=Path)
    parser.add_argument('--cache-root', type=Path, default=Path.home()/'Library/Caches/nsp-dawrin')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--engine', default='auto')
    parser.add_argument('--shaders',choices=('runtime','prewarm'),default='runtime')
    parser.add_argument('--update', type=Path, action='append', default=[])
    parser.add_argument('--dlc', type=Path, action='append', default=[])
    parser.add_argument('--application-id', type=lambda value:int(value,16))
    parser.add_argument('--inspect', action='store_true', help='Show selected content without preparing or launching')
    args = parser.parse_args()
    tools = Path(__file__).resolve().parent
    package = ContentSet([args.package,*args.update,*args.dlc],args.keys,args.application_id)
    if args.inspect:
        try: print(json.dumps(package.describe(),indent=2))
        finally: package.close()
        return
    cache = args.cache_root.resolve()/package.title_id
    stamp = dict(content=[dict(path=str(c.path),size=c.size,modified_ns=c.path.stat().st_mtime_ns) for c in package.containers],
                 selection=package.describe(),
                 engine=args.engine, shaders=args.shaders, rewriter=hashlib.sha256((tools/'patch_nso.py').read_bytes()).hexdigest())
    receipt = cache/'prepared.json'
    fresh = not receipt.exists() or json.loads(receipt.read_text()) != stamp
    try:
        if fresh:
            if receipt.exists():
                raise RuntimeError('Package or rewriter changed; use a fresh cache root to preserve existing saves')
            package.prepare(cache)
            for name in ('main', *(f'subsdk{i}' for i in range(10)), 'sdk'):
                source = cache/'ExeFS'/name
                if source.exists():
                    subprocess.run([sys.executable, str(tools/'patch_nso.py'), str(source), str(cache/'patched'), name], check=True)
            (cache/'shaders').mkdir(exist_ok=True)
            if args.shaders=='prewarm':
                from scan_shaders import scan
                report=scan(package,cache/'shaders',args.engine)
                if not report['complete']:raise RuntimeError('Engine prewarm scan is incomplete; see scan-report.json')
            receipt.write_text(json.dumps(stamp, indent=2))
        if args.shaders=='prewarm':
            subprocess.run([sys.executable,str(tools/'compile_pending_shaders.py'),str(cache/'shaders')],check=True)
    finally:
        package.close()
    if args.prepare_only:
        print(cache)
        return
    env = dict(os.environ, GAME_DIR=str(cache), DM_WINDOW='1', DM_TIMEOUT='0', DM_AUDIO='1')
    os.execve(sys.executable, [sys.executable, str(tools/'run_with_report.py'), '--', str(tools.parent/'run.sh')], env)


if __name__ == '__main__':
    main()
