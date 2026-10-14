"""Prepare a versioned shader cache through replaceable translation backends."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
from nsp_runtime.backends import MaxwellSpirvBackend, MetalSourceBackend
from nsp_runtime.cache import TOOLS, atomic_write, chain_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--key')
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'compile.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cross = shutil.which('spirv-cross') or '/opt/homebrew/bin/spirv-cross'
        chain = chain_version(directory, cross)
        subprocess.run([sys.executable, str(TOOLS/'prepare_shaders.py'), str(directory), '--chain', chain],
                       check=True, timeout=120)
        jobs = json.loads((directory/'jobs.json').read_text())
        selected = [job for job in jobs if not args.key or job['key'] == args.key]
        if args.key and not selected:
            raise RuntimeError('Requested shader has no captured control/code pair')
        translated = MaxwellSpirvBackend().translate(selected, directory/'translated'/chain)
        atomic_write(directory/'translation-failures.json', json.dumps(translated.failed, indent=2))
        built = MetalSourceBackend(chain, cross).build(directory)
        report = dict(chain=chain, requested=len(selected), translated=len(translated.completed),
                      ready=len(built.completed), translation_failures=translated.failed, binding_failures=built.failed)
        atomic_write(directory/'build-report.json', json.dumps(report, indent=2))
        if args.key:
            if args.key not in built.completed:
                raise RuntimeError('Requested shader is not ready; see build-report.json')
        elif translated.failed or built.failed:
            raise RuntimeError('Shader preparation is incomplete; see build-report.json')


if __name__ == '__main__':
    main()
