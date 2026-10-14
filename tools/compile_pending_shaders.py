"""Prepare a versioned shader cache through replaceable translation backends."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
from nsp_runtime.backends import MaxwellSpirvBackend, MetalSourceBackend
from shader_jobs import prepare, prepare_observed
from nsp_runtime.cache import TOOLS, atomic_write, chain_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--key')
    parser.add_argument('--source-key')
    parser.add_argument('--facts', type=Path)
    parser.add_argument('--observed', action='store_true',
                        help='Rebuild all previously observed variants from captured code and validated runtime facts')
    args = parser.parse_args()
    if args.observed and (args.key or args.source_key or args.facts):
        parser.error('--observed cannot be combined with a single-variant request')
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'compile.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cross = shutil.which('spirv-cross') or '/opt/homebrew/bin/spirv-cross'
        chain = chain_version(directory, cross)
        facts=json.loads(args.facts.read_text()) if args.facts else None
        if args.observed:
            selected, capture_failures = prepare_observed(directory, chain)
        else:
            selected,capture_failures=prepare(directory,chain,args.source_key or args.key,
                                              args.key if args.source_key else None,facts)
        translated = MaxwellSpirvBackend().translate(selected, directory/'translated'/chain)
        atomic_write(directory/'translation-failures.json', json.dumps(translated.failed, indent=2))
        built = MetalSourceBackend(chain, cross).build(directory, args.key)
        report = dict(chain=chain, requested=len(selected), translated=len(translated.completed),
                      ready=len(built.completed), capture_failures=capture_failures, translation_failures=translated.failed, binding_failures=built.failed)
        atomic_write(directory/'build-report.json', json.dumps(report, indent=2))
        if args.key:
            if args.key not in built.completed:
                raise RuntimeError('Requested shader is not ready; see build-report.json')
        elif capture_failures or translated.failed or built.failed:
            raise RuntimeError('Shader preparation is incomplete; see build-report.json')


if __name__ == '__main__':
    main()
