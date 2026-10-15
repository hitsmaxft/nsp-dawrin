"""Host file operations shared by package readers, independent of package formats."""
import os
from threading import Lock

_pread = getattr(os, 'pread', None)


class PositionalReader:
    """Owned binary descriptor with serialized read/close and positional reads.

    POSIX uses pread. Hosts without it use seek/read under the same per-file lock,
    so concurrent callers cannot change one another's offsets. A short read is
    returned to the format layer for its own truncation/error policy.
    """
    def __init__(self, path):
        self._lock = Lock()
        self._fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
        try:
            self.size = os.fstat(self._fd).st_size
        except BaseException:
            self.close()
            raise

    def read_at(self, offset, size):
        if offset < 0 or size < 0:
            raise ValueError('Negative file range')
        with self._lock:
            if self._fd < 0:
                raise ValueError('Reader is closed')
            if _pread is not None:
                return _pread(self._fd, size, offset)
            os.lseek(self._fd, offset, os.SEEK_SET)
            return os.read(self._fd, size)

    def close(self):
        with self._lock:
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1
