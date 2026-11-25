# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


def build_report() -> None: ...  # the work of yours that one process at a time may do


with cache.lock("report", ttl=30):
    build_report()


# --8<-- [end:show]
