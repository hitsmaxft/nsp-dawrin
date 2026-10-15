"""Stage and build the Flutter desktop client under the root build directory."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flutter', default='flutter')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    flutter = shutil.which(args.flutter)
    if not flutter:
        parser.error('Install Flutter or provide --flutter /path/to/flutter')
    stage = ROOT / 'build/flutter/project'
    stage.mkdir(parents=True, exist_ok=True)
    ignored = {'build', '.dart_tool', 'ephemeral', '.plugin_symlinks', 'Pods', '.symlinks', '.git', '.idea'}
    for source in (ROOT / 'gui').rglob('*'):
        relative = source.relative_to(ROOT / 'gui')
        if any(part in ignored for part in relative.parts) or source.name.startswith('.flutter-plugins'):
            continue
        if source.is_file():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or source.read_bytes() != target.read_bytes():
                shutil.copy2(source, target)
    env = dict(os.environ, PUB_CACHE=str(ROOT / 'build/pub-cache'))
    def run(*command):
        subprocess.run([flutter, *command], cwd=stage, env=env, check=True)
    run('pub', 'get')
    if args.test:
        run('analyze')
        run('test', '--reporter', 'expanded')
    if args.build or not args.test:
        target = {'darwin': 'macos', 'win32': 'windows'}.get(sys.platform, 'linux')
        run('build', target, '--release')
        print(f'Desktop build: {stage / "build" / target}')


if __name__ == '__main__':
    main()
