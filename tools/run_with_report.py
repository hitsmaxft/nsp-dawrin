"""Supervise a native session and offer a report after an abnormal exit."""
import argparse
from collections import deque
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
from crash_report import ROOT, MAX_LOG_BYTES, build_identity, create_report, exit_kind
from smoke import query


class LogTail:
    def __init__(self):
        self.parts = deque()
        self.size = 0

    def append(self, data):
        self.parts.append(data); self.size += len(data)
        while self.size > MAX_LOG_BYTES:
            excess = self.size-MAX_LOG_BYTES
            first = self.parts.popleft()
            if len(first) > excess:
                self.parts.appendleft(first[excess:]); self.size -= excess
            else:
                self.size -= len(first)

    def text(self):
        return b''.join(self.parts).decode('utf-8', 'replace')


def supervise(command, output_root=None, show=True, echo=False):
    identity = build_identity()
    tail = LogTail()
    status, settings = {}, {}
    interrupted = False
    with tempfile.TemporaryDirectory(prefix='nsp-session-', dir='/tmp') as temporary:
        env = dict(os.environ)
        env.setdefault('DM_CONTROL', str(Path(temporary)/'control.sock'))
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        def drain():
            while True:
                chunk = process.stdout.read1(16384)
                if not chunk:
                    break
                tail.append(chunk)
                if echo:
                    try:
                        sys.stdout.buffer.write(chunk); sys.stdout.buffer.flush()
                    except (BrokenPipeError, OSError):
                        pass
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        def stop(number, frame):
            nonlocal interrupted
            interrupted = True
            try:
                os.killpg(process.pid, number)
            except ProcessLookupError:
                pass
        handlers = {number:signal.signal(number, stop) for number in (signal.SIGINT,signal.SIGTERM)}
        try:
            while process.poll() is None:
                try:
                    current = query(env['DM_CONTROL'], 'status')
                    if current.get('pid') == process.pid:
                        status = current
                        settings = query(env['DM_CONTROL'], 'settings')
                except (OSError, ValueError, RuntimeError):
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            for number, handler in handlers.items():
                signal.signal(number, handler)
            # Only descendants in this supervisor's dedicated process group are affected.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            reader.join(timeout=2)
            if reader.is_alive():
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                reader.join(timeout=2)
            process.stdout.close()
    code = process.returncode
    path = None
    if not interrupted and exit_kind(code) not in ('normal','stopped','timeout'):
        path = create_report(tail.text(), code, output_root, status=status, settings=settings, identity=identity)
        print(f'Crash report: {path}', file=sys.stderr)
        if show:
            reporter = Path(os.environ.get('NSP_CRASH_REPORTER', ROOT.parent/'work/bin/crash-report'))
            try:
                subprocess.Popen([str(reporter), str(path)], start_new_session=True)
            except OSError as error:
                print(f'Report window unavailable: {error}. Open agent-prompt.md beside report.json.', file=sys.stderr)
    return code, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-ui', action='store_true')
    parser.add_argument('--echo', action='store_true')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--': command = command[1:]
    code, _ = supervise(command or [str(ROOT/'run.sh')], args.output_root, not args.no_ui, args.echo)
    return code if code >= 0 else 128-code


if __name__ == '__main__':
    raise SystemExit(main())
