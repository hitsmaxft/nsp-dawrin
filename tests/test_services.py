from pathlib import Path
import sys
import unittest
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from service_catalog import catalog

class ServiceTests(unittest.TestCase):
    def test_alias_conflicts_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'src').mkdir()
            (root/'src/alias.c').write_text('HLE_GUEST_ALIAS("source", "target", "reason", example)\n')
            (root/'src/host.c').write_text('HLE_FORCE("source", "reason", void, implementation, void) {}\n')
            result=catalog(root);self.assertEqual(len(result['conflicts']),1)
            self.assertEqual(result['conflicts'][0]['symbol'],'source')

    def test_host_bindings_are_unique_and_use_shared_services(self):
        result=catalog();self.assertFalse(result['conflicts'])
        bindings={row['symbol']:row for row in result['bindings']}
        for name in ('_ZN2nn3aoc17CountAddOnContentEv','_ZN2nn3aoc16ListAddOnContentEPiii',
                     '_ZN2nn2fs15GetSaveDataSizeEPlS1_RKNS_7account3UidE'):
            self.assertIn(name,bindings)
        self.assertNotIn('_ZN2nn3aoc16CountAddOnContentEv',bindings)
        # Media HeapObject allocations share the SDK's graphics allocator state.
        # Recording only host callbacks leaves NvOsAlloc without its allocator.
        for name in bindings:
            self.assertNotIn('SetGraphicsAllocator',name)
            self.assertNotIn('SetGraphicsDevtoolsAllocator',name)

if __name__=='__main__':unittest.main()
