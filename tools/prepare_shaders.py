"""Prepare isolated offline jobs from runtime or engine captures."""
import argparse
from pathlib import Path
from nsp_runtime.cache import chain_version
from shader_jobs import prepare

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--chain');parser.add_argument('--key')
    args=parser.parse_args()
    jobs,failures=prepare(args.directory.resolve(),args.chain or chain_version(args.directory),args.key)
    print(f'Prepared {len(jobs)} shader jobs; {len(failures)} unsupported captures')
    raise SystemExit(bool(failures))
