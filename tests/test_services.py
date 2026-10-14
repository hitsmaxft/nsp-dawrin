from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from service_catalog import catalog

class ServiceTests(unittest.TestCase):
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
