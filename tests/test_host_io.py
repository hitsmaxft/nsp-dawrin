from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from host_io import PositionalReader


class HostIoTests(unittest.TestCase):
    def check_reads(self, path, content):
        reader = PositionalReader(path)
        try:
            self.assertEqual(reader.size, len(content))
            def read(index):
                start = index * 37 % (len(content) - 257)
                self.assertEqual(reader.read_at(start, 257), content[start:start + 257])
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(read, range(400)))
            self.assertEqual(reader.read_at(len(content) - 2, 10), content[-2:])
            self.assertEqual(reader.read_at(0, 0), b'')
            with self.assertRaises(ValueError):
                reader.read_at(-1, 1)
        finally:
            reader.close()
        reader.close()
        with self.assertRaisesRegex(ValueError, 'closed'):
            reader.read_at(0, 1)

    def test_native_and_seek_fallback_preserve_binary_offsets(self):
        content = bytes(range(256)) * 32
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bytes.bin'
            path.write_bytes(content)
            self.check_reads(path, content)
            with patch('host_io._pread', None):
                self.check_reads(path, content)


if __name__ == '__main__':
    unittest.main()
