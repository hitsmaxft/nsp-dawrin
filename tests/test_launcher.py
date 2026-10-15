"""Desktop API contracts against original packages and owned child processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fixture_app import build
from launcher.service import Launcher, ROOT
from launcher.store import preferences, native_preferences


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        build(self.root/'packages'); self.service=Launcher(self.root/'data')
        self.service.dispatch('config.update',dict(patch={'keys':str(self.root/'packages/fixture.keys')}))

    def tearDown(self):
        self.service.close(); self.temp.cleanup()

    def add(self):
        result=self.service.dispatch('library.add',dict(path=str(self.root/'packages/base.nsp')))
        return result['library'][0]

    def wait(self):
        self.service.worker.join(timeout=20)
        self.assertFalse(self.service.worker.is_alive())
        return self.service.snapshot()['session']

    def test_library_associations_and_preferences_are_atomic(self):
        entry=self.add()
        with self.assertRaisesRegex(ValueError,'already'): self.add()
        with self.assertRaisesRegex(ValueError,'newer'):
            self.service.dispatch('library.update',dict(id=entry['id'],patch={'dlc':[str(self.root/'packages/addon.nsp')]}))
        self.assertEqual(self.service.store.entry(entry['id'])['dlc'],[])
        result=self.service.dispatch('library.update',dict(id=entry['id'],patch={
            'updates':[str(self.root/'packages/update.nsp')],'dlc':[str(self.root/'packages/addon.nsp')],
            'preferences':preferences({'mode':'console','resolution':1080})}))
        self.assertEqual(result['library'][0]['description']['application_version'],2)
        self.service.dispatch('session.prepare',dict(id=entry['id']))
        self.assertEqual(self.wait()['state'],'ready')
        self.assertEqual(len(list((self.root/'data/cache').rglob('main.patched.bin'))),1)
        self.assertEqual(Launcher(self.root/'data').snapshot()['library'],result['library'])
        self.service.dispatch('library.remove',dict(id=entry['id']))
        self.assertTrue((self.root/'packages/base.nsp').exists())
        self.assertTrue(list((self.root/'data/cache').rglob('main.patched.bin')))

    def test_keyboard_conflicts_and_private_storage_boundaries(self):
        value=preferences({}); native=native_preferences(value)
        self.assertEqual(native['bindings']['0'],[6,49])
        value['bindings']['1']=[29]
        with self.assertRaisesRegex(ValueError,'already'): preferences(value)
        with self.assertRaises(ValueError): self.service.dispatch('config.update',dict(patch={'cache':str(ROOT/'build')}))
        with self.assertRaises(ValueError): self.service.dispatch('config.update',dict(patch={'unknown':'value'}))
        self.assertNotIn('header_key',json.dumps(self.service.snapshot()))

    def test_stdio_protocol_and_eof_shutdown(self):
        with subprocess.Popen([sys.executable,str(ROOT/'tools/launcher_service.py'),'--data-dir',str(self.root/'rpc')],
                              stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as child:
            requests=[dict(version=1,id=1,method='snapshot'),dict(version=9,id=2,method='snapshot')]
            out,err=child.communicate('\n'.join(map(json.dumps,requests))+'\n',timeout=10)
            self.assertEqual(child.returncode,0,err)
            replies=[json.loads(line) for line in out.splitlines()]
            self.assertEqual(replies[0]['result']['capabilities']['protocol'],1)
            self.assertIn('error',replies[1])

    def test_stop_terminates_only_the_owned_child(self):
        import threading
        self.service.session['state']='preparing'
        def work():
            try: self.service._child([sys.executable,'-c','import time; time.sleep(30)'])
            except InterruptedError: pass
        self.service.worker=threading.Thread(target=work)
        self.service.worker.start()
        deadline=time.monotonic()+3
        while self.service.process is None and time.monotonic()<deadline: time.sleep(.01)
        process=self.service.process; self.assertIsNotNone(process)
        self.service.dispatch('session.stop',{})
        self.service.worker.join(timeout=5)
        self.assertIsNotNone(process.poll())
        self.assertFalse(self.service.worker.is_alive())


if __name__=='__main__': unittest.main()
