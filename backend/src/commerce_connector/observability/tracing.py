from contextlib import contextmanager
from time import perf_counter
@contextmanager
def span(name):
    start=perf_counter()
    try: yield
    finally: _duration_ms=(perf_counter()-start)*1000
