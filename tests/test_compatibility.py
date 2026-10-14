import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from compatibility import classify,group
from validate_matrix import cases_from,validate

class CompatibilityTests(unittest.TestCase):
    def test_ipc_commands_and_registration_conflicts(self):
        gap=classify({'outcome':'process_exited'},'Unsupported IPC command: set:999')
        self.assertEqual(gap,dict(category='ipc-command',key='set:999'))
        with patch('validate_matrix.catalog',return_value={'conflicts':[{}]}):
            with self.assertRaisesRegex(ValueError,'Conflicting'):validate([],Path('/unused'))

    def test_shared_interface_group_and_private_data(self):
        log='private path /Users/person/secret.nsp\n[dm] FATAL unsupported import _ZN2nn2fsExampleEv (x0=0x123)'
        gap=classify({'outcome':'process_exited'},log)
        self.assertEqual(gap,dict(category='service',key='_ZN2nn2fsExampleEv'))
        self.assertEqual(group([dict(id=x,classification=gap) for x in ('a','b')])[0]['cases'],['a','b'])
        self.assertNotIn('secret',json.dumps(gap))

    def test_matrix_continues_and_persists_after_case_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=root/'cases.json'
            manifest.write_text(json.dumps(dict(cases=[dict(id='bad',cache='/private/bad'),dict(id='good',cache='/private/good')])))
            def run(cache,timeout,output):
                if cache.name=='bad':raise ValueError('Missing local key: test_key')
                (output/'runtime.log').write_text('private data')
                return dict(outcome='rendering_started',last_status=dict(frames=45,pid=123),seconds=1)
            result=validate(cases_from(manifest),root/'results',run)
            self.assertTrue(result['complete']);self.assertEqual(len(result['groups']),1)
            self.assertEqual(result['groups'][0]['category'],'prerequisite')
            self.assertNotIn('/private',json.dumps(result));self.assertNotIn('pid',result['results'][1]['counters'])
            manifest.write_text(json.dumps(dict(cases=[dict(id='../bad',cache='x')])))
            with self.assertRaises(ValueError):cases_from(manifest)

if __name__=='__main__':unittest.main()
