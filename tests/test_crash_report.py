"""Check disclosure boundaries, bounded capture, and abnormal-exit supervision."""
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from crash_report import MAX_LOG_BYTES, collect, create_report, exit_kind
from run_with_report import LogTail, supervise

IDENTITY = dict(revision='a'*40, modified=False)
LOG = '''private path /Users/person/private/game.nsp
prod.keys secret=do-not-share-this-token
[dm] native fault signal=11 address=0x1234 pc=sdk+0x200
[dm] registers x0=0x1234
[dm] nearest symbol _ZN2nn2fs15GetSaveDataSizeEPlS1_RKNS_7account3UidE+0xc0
[dm] frame 0: main+0x400
'''


class CrashReportTests(unittest.TestCase):
    def test_shareable_report_has_no_raw_log_or_device_preferences(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = create_report(LOG, 139, temporary, identity=IDENTITY,
                                 status=dict(frames=23, shader_loads=4, path='/private'),
                                 settings=dict(active_mode='handheld', controller={'vendor':'private device'}, resolution=720))
            payload = json.loads(path.read_text())
            for filename in ('report.json', 'issue.md', 'agent-prompt.md'):
                text = (path.parent/filename).read_text()
                for secret in ('/Users/person','do-not-share-this-token','private device','registers x0'):
                    self.assertNotIn(secret, text)
                self.assertEqual(stat.S_IMODE((path.parent/filename).stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertIn('do-not-share-this-token', (path.parent/'runtime.log').read_text())
            self.assertEqual(payload['diagnostics']['fault']['location'], 'sdk+0x200')
            self.assertEqual(payload['diagnostics']['runtime']['frames'], 23)
            url = urlsplit(payload['issue_url']); query = parse_qs(url.query)
            self.assertEqual(url.netloc, 'github.com')
            self.assertEqual(query['body'][0], payload['issue_body'])
            self.assertEqual(query['template'], ['crash-report.md'])
            self.assertIn('AGENTS.md', payload['agent_prompt'])
            self.assertIn('tools/smoke.py', payload['agent_prompt'])

    def test_fingerprint_ignores_host_aslr_but_tracks_guest_locations(self):
        a = collect('[dm] native fault signal=11 address=0x0 pc=host+0x123',139,identity=IDENTITY)
        b = collect('[dm] native fault signal=11 address=0x0 pc=host+0x456',139,identity=IDENTITY)
        self.assertEqual(a['fingerprint'],b['fingerprint'])
        b = collect('[dm] native fault signal=11 address=0x0 pc=sdk+0x456',139,identity=IDENTITY)
        self.assertNotEqual(a['fingerprint'],b['fingerprint'])

    def test_log_tail_bounds_and_exit_classification(self):
        tail=LogTail();tail.append(b'a'*MAX_LOG_BYTES);tail.append(b'b'*100)
        self.assertEqual(tail.size,MAX_LOG_BYTES)
        self.assertEqual(tail.text(), 'a'*(MAX_LOG_BYTES-100)+'b'*100)
        for code,kind in [(0,'normal'),(-15,'stopped'),(143,'stopped'),(-14,'timeout'),(-6,'signal'),(139,'signal'),(2,'launch_failure')]:
            self.assertEqual(exit_kind(code),kind)

    def test_supervisor_reports_crash_without_launching_ui(self):
        with tempfile.TemporaryDirectory() as temporary:
            code,path=supervise([sys.executable,'-c',f'print({LOG!r},flush=True);raise SystemExit(139)'],temporary,show=False)
            self.assertEqual(code,139);self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())['diagnostics']['fault']['signal'],11)
            for script in ('raise SystemExit(0)', 'import os,signal;os.kill(os.getpid(),signal.SIGTERM)',
                           'import os,signal;os.kill(os.getpid(),signal.SIGALRM)'):
                _,path=supervise([sys.executable,'-c',script],temporary,show=False)
                self.assertIsNone(path)
            self.assertEqual(len(list(Path(temporary).iterdir())),1)

    def test_parent_stop_forwards_to_owned_child_without_reporting(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker=Path(temporary)/'child.pid';reports=Path(temporary)/'reports'
            script=f'import os,time;open({str(marker)!r},"w").write(str(os.getpid()));time.sleep(20)'
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/run_with_report.py'),
                '--no-ui','--output-root',str(reports),'--',sys.executable,'-c',script],stderr=subprocess.PIPE)
            try:
                limit=time.monotonic()+5
                while not marker.exists() and time.monotonic()<limit:time.sleep(.02)
                self.assertTrue(marker.exists())
                pid=int(marker.read_text());process.terminate();process.wait(timeout=5)
                with self.assertRaises(ProcessLookupError):os.kill(pid,0)
                self.assertFalse(reports.exists())
            finally:
                if process.poll() is None:process.kill();process.wait()
                process.stderr.close()


if __name__ == '__main__':unittest.main()
