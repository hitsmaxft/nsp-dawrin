"""Exercise diagnostics against private paths, fragmented replies, and failures."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from shader_report import report
from smoke import first_failure, query


class DiagnosticsTests(unittest.TestCase):
    def test_conversion_report_excludes_private_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = '0123456789abcdef'
            (root/'build-report.json').write_text(json.dumps(dict(
                chain=key, requested=1, ready=0,
                translation_failures={key:'Secret input from /private/package.nsp'},
                binding_failures={})))
            (root/'scan-report.json').write_text(json.dumps(dict(
                errors=['/private/package.nsp'], shader_keys=[key], complete=False)))
            result = report(root)
            self.assertEqual(result['translation_failure_keys'], [key])
            self.assertEqual(result['scan']['errors'], 1)
            self.assertNotIn('/private/', json.dumps(result))
            self.assertNotIn('Secret input', json.dumps(result))

    def test_control_protocol_accepts_fragmented_reply(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            path = Path(temporary)/'socket'
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path)); server.listen(1)
                def reply():
                    with server.accept()[0] as client:
                        self.assertEqual(client.recv(100), b'status\n')
                        client.sendall(b'{"frames":')
                        client.sendall(b'42}\n')
                worker = threading.Thread(target=reply)
                worker.start()
                self.assertEqual(query(path, 'status'), {'frames':42})
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive())

    def test_diagnostics_keep_first_failure(self):
        log = 'startup complete\nnative fault signal=11\nAssertion while shutting down\n'
        self.assertEqual(first_failure(log), 'native fault signal=11')
        self.assertIsNone(first_failure('ordinary startup\n'))


if __name__ == '__main__':
    unittest.main()
