import gc

class IterStream:
    def __init__(self,iterable):
        self._iter = iterable
        self._left = b''
        self._l_buffer = []
    def readable(self):
        return True

    def read1(self, n=None):
        while not self._left:
            try:
                self._left = next(self._iter)
            except StopIteration:
                break
        ret = self._left[:n]
        self._left = self._left[len(ret):]
        return ret

    def prefetch(self, n_bytes):
        while len(self._left) < n_bytes:
            try:
                self._left = self._left + next(self._iter)
            except StopIteration:
                break

    def read(self, n=None):
        # This is wonky, but I think it helps reduce memory fragmentation?
        l = self._l_buffer
        l.clear()
        if n is None or n < 0:
            while True:
                m = self.read1()
                if not m:
                    break
                l.append(m)
        else:
            while n > 0:
                m = self.read1(n)
                if not m:
                    break
                n -= len(m)
                l.append(m)
        return b''.join(l)