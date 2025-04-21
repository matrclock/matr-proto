import time
import errno

class SafeIterStream:
    def __init__(self, iterator, retries=3, delay=0.1):
        self.iterator = iterator
        self.retries = retries
        self.delay = delay

    def __iter__(self):
        return self

    def __next__(self):
        for attempt in range(self.retries):
            try:
                return next(self.iterator)
            except OSError as e:
                if getattr(e, "errno", None) == errno.EBADF:
                    print(f"[retry] EBADF (bad file descriptor), retrying {attempt + 1}")
                    time.sleep(self.delay)
                else:
                    raise
            except StopIteration:
                raise
        print("[fail] Giving up after retries")
        raise StopIteration()
