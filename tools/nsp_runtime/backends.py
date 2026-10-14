"""Bounded process adapters for offline translation and Metal source generation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .cache import TOOLS, atomic_write
from .interfaces import BackendResult


class MaxwellSpirvBackend:
    name = 'maxwell-spirv'

    def translate(self, jobs, directory):
        directory.mkdir(parents=True, exist_ok=True)
        dotnet = os.environ.get('DOTNET') or shutil.which('dotnet') or str(TOOLS.parents[1]/'work/dotnet/dotnet')
        compiler = TOOLS/'shader_translate/bin/Release/net10.0/dmsh_xlate.dll'
        source_sha = hashlib.sha256(b''.join((TOOLS/'shader_translate'/name).read_bytes()
                                            for name in ('Program.cs', 'dmsh_xlate.csproj'))).hexdigest()[:16]
        actual = subprocess.check_output([dotnet, str(compiler), '--source-sha'], text=True, timeout=15).strip()
        if actual != source_sha:
            raise RuntimeError('Translator binary does not match its source; rebuild it first')
        fingerprints = {job['key']: hashlib.sha256(
            json.dumps({k: v for k, v in job.items() if k != 'code'}, sort_keys=True).encode()
            + Path(job['code']).read_bytes()).hexdigest() for job in jobs}
        def ready(job):
            receipt = directory/(job['key']+'.receipt')
            return (receipt.exists() and receipt.read_text() == fingerprints[job['key']]
                    and all((directory/(job['key']+suffix)).is_file() for suffix in ('.spv', '.res.json')))
        for job in jobs:
            if not ready(job):
                for suffix in ('.spv', '.res.json', '.receipt'):
                    (directory/(job['key']+suffix)).unlink(missing_ok=True)
        failures = {}
        for debug in (False, True):
            pending = [dict(job, debug=debug) for job in jobs if not ready(job)]
            for start in range(0, len(pending), 128):
                batch = pending[start:start+128]
                target = directory/'pending.json'
                atomic_write(target, json.dumps(batch))
                try:
                    result = subprocess.run([dotnet, str(compiler), str(target), str(directory)],
                                            capture_output=True, text=True, timeout=120)
                    detail = result.stderr[-4000:] or f'Translator exited {result.returncode}'
                except subprocess.TimeoutExpired:
                    detail = 'Translation batch timed out after 120 seconds'
                for job in batch:
                    if all((directory/(job['key']+suffix)).is_file() for suffix in ('.spv', '.res.json')):
                        atomic_write(directory/(job['key']+'.receipt'), fingerprints[job['key']])
                    if not ready(job):
                        failures[job['key']] = detail
        return BackendResult([j['key'] for j in jobs if ready(j)],
                             {j['key']: failures.get(j['key'], 'Translation output missing') for j in jobs if not ready(j)})


class MetalSourceBackend:
    name = 'metal-source'

    def __init__(self, chain, cross):
        self.chain, self.cross = chain, cross

    def build(self, directory, key=None):
        subprocess.run([sys.executable, str(TOOLS/'build_metal.py'), str(directory),
                        '--chain', self.chain, '--spirv-cross', self.cross]+(['--key',key] if key else []), check=True, timeout=900)
        failures = json.loads((directory/'binding-failures.json').read_text())
        completed = [line.split('\t')[1] for line in (directory/'shader_map.tsv').read_text().splitlines()
                     if line and not line.startswith('#')]
        return BackendResult(completed, {item['key']: item['error'] for item in failures})
