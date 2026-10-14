"""Fingerprint the actual conversion chain and publish complete files atomically."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

TOOLS = Path(__file__).resolve().parents[1]
OPTIONS = {'schema': 2, 'msl': 23000, 'argument_buffers': True, 'debug': False,
           'debug_retry': True, 'reduced': False, 'binding_abi': 'macos-1'}


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.tmp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data.encode() if isinstance(data, str) else data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest_files(files, options):
    digest = hashlib.sha256(json.dumps(options, sort_keys=True).encode())
    for label, path in sorted(files.items()):
        digest.update(label.encode()+b'\0')
        with Path(path).open('rb') as stream:
            while chunk := stream.read(1024*1024):
                digest.update(chunk)
        digest.update(b'\0')
    return digest.hexdigest()[:16]


def chain_version(directory, cross=None):
    cross = cross or shutil.which('spirv-cross') or '/opt/homebrew/bin/spirv-cross'
    compiler = TOOLS/'shader_translate/bin/Release/net10.0'
    files = {str(path.relative_to(TOOLS)): path for path in (TOOLS/'nsp_runtime').rglob('*.py')}
    for name in ('prepare_shaders.py', 'build_metal.py', 'compile_pending_shaders.py',
                 'shader_jobs.py', 'shader_translate/Program.cs', 'shader_translate/dmsh_xlate.csproj'):
        files[name] = TOOLS/name
    for path in compiler.glob('*.dll'):
        files['compiler/'+path.name] = path
    if not (compiler/'dmsh_xlate.dll').is_file():
        raise RuntimeError('Build the offline translator before preparing or launching shaders')
    files['spirv-cross'] = Path(cross)
    for name in ('nvn_refl.h', 'nvn_refl.m', 'nvn_mtl.m', 'nvn_runtime_facts.inc', 'hle_nvn.c',
                 'nvn_draw.h', 'nvn_obj.h'):
        files['binding/'+name] = TOOLS.parent/'src/gfx/nvn'/name
    facts = Path(directory)/'shader-facts.json'
    if facts.exists():
        files['shader-facts'] = facts
    return digest_files(files, OPTIONS)
