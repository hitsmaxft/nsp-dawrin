"""Export bounded shader diagnostics without source blobs or local file paths."""
import argparse
import json
import platform
from pathlib import Path
import re
import subprocess


def report(directory):
    def read(name, default):
        path = directory/name
        return json.loads(path.read_text()) if path.exists() else default
    build = read('build-report.json', {})
    scan = read('scan-report.json', {})
    facts = read('facts-report.json', {})
    chain = build.get('chain', '')
    metal = read(f'metal/b-{chain}/metal-validation.json', {}) if re.fullmatch('[0-9a-f]{16}', chain) else {}
    def keys(value):
        items = value.keys() if isinstance(value, dict) else (row.get('key', '') for row in value if isinstance(row, dict))
        return sorted(key for key in items if re.fullmatch('[0-9a-f]{16}', key))
    try:
        revision = subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[1]),
                                            'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = 'unknown'
    return dict(schema_version=1, revision=revision,
                host=dict(system=platform.system(), release=platform.release(), architecture=platform.machine(), python=platform.python_version()),
                engine=scan.get('engine', 'unknown'), chain=chain if re.fullmatch('[0-9a-f]{16}', chain) else 'unknown',
                scan=dict(keys=len(scan.get('shader_keys', [])), errors=len(scan.get('errors', [])),
                          unsupported=len(scan.get('unsupported_stages', [])), complete=scan.get('complete', False)),
                facts=dict(total=len(facts), incomplete=sum(not value.get('complete', False) for value in facts.values())),
                build={name:build.get(name, 0) for name in ('requested', 'translated', 'ready')},
                translation_failure_keys=keys(build.get('translation_failures', {})),
                binding_failure_keys=keys(build.get('binding_failures', {})),
                metal=dict(sources=metal.get('sources', 0), unique=metal.get('unique', 0), failures=len(metal.get('failures', []))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(report(args.directory), indent=2))
