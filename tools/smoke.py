"""Run a bounded startup check using the native control API and a private log."""
import argparse
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import tempfile
import time


def query(path, command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        connection.connect(str(path))
        connection.sendall((command+'\n').encode())
        data = bytearray()
        while b'\n' not in data:
            part = connection.recv(4096)
            if not part or len(data) + len(part) > 16384:
                raise RuntimeError('Invalid control response')
            data.extend(part)
        response = json.loads(data)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response


def first_failure(log):
    for line in log.splitlines():
        if any(marker in line for marker in ('native fault', 'ASSERT', 'Assertion',
                                             '【红】', 'unimplemented', 'Unsupported', 'Traceback', 'Break#', 'FATAL')):
            return line[:1000]
    return None


def run(game_dir, timeout=90, frames=30, stable_seconds=3, output=None):
    root = Path(__file__).resolve().parents[1]
    game_dir = game_dir.resolve()
    output = (output or game_dir/'validation').resolve()
    if output.is_relative_to(root):
        raise ValueError('Validation output must be outside the source checkout')
    if not (game_dir/'patched/main.patched.bin').is_file():
        raise ValueError('Prepared executable is missing')
    output.mkdir(parents=True, exist_ok=True)
    result = dict(schema_version=1, outcome='timeout', seconds=0, last_status={},
                  input_acknowledged=False, samples=[], first_failure=None)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='nsp-smoke-', dir='/tmp') as temporary:
        control = Path(temporary)/'control.sock'
        env = dict(os.environ, GAME_DIR=str(game_dir), DM_WINDOW='1',
                   DM_TIMEOUT=str(int(timeout)+5), DM_CONTROL=str(control))
        with (output/'runtime.log').open('w') as log:
            process = subprocess.Popen([str(root/'run.sh')], env=env, stdout=log,
                                       stderr=subprocess.STDOUT,start_new_session=True)
            baseline = None
            try:
                while time.monotonic()-started < timeout:
                    if process.poll() is not None:
                        result.update(outcome='process_exited', returncode=process.returncode)
                        break
                    try:
                        status = query(control, 'status')
                    except (OSError, ValueError, RuntimeError):
                        time.sleep(0.25)
                        continue
                    if status.get('pid') != process.pid:
                        raise RuntimeError('Control socket process does not match launched host')
                    now = time.monotonic()
                    result['last_status'] = status
                    result['samples'].append(dict(seconds=round(now-started, 2), **status))
                    if status.get('shader_failures', 0):
                        result['outcome'] = 'shader_failure'
                        break
                    ready = status.get('frames', 0) >= frames and status.get('shader_loads', 0) > 0
                    if ready and baseline is None:
                        # A neutral button report exercises the input API without changing a save/menu.
                        result['input_acknowledged'] = query(control, 'buttons 0').get('ok', False)
                        baseline = (now, status['frames'])
                    elif baseline and now-baseline[0] >= stable_seconds:
                        if status['frames'] > baseline[1] and result['input_acknowledged']:
                            result['outcome'] = 'rendering_started'
                            break
                        baseline = (now, status['frames'])
                    time.sleep(0.5)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL)
                        process.wait(timeout=3)
                # Reap compiler descendants belonging to this test after host failure.
                try: os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError: pass
    result['seconds'] = round(time.monotonic()-started, 2)
    result['first_failure'] = first_failure((output/'runtime.log').read_text(errors='replace'))
    (output/'smoke.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game_dir', type=Path)
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--stable-seconds', type=float, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.timeout <= 0 or args.frames < 1 or args.stable_seconds <= 0:
        parser.error('Timeout, frame threshold, and stable duration must be positive')
    result = run(**vars(args))
    print(json.dumps({key:value for key,value in result.items() if key != 'samples'}, indent=2))
    return 0 if result['outcome'] == 'rendering_started' else 1


if __name__ == '__main__':
    raise SystemExit(main())
