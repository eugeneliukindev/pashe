# --8<-- [start:show]
from pashe import Locks
from pashe.backends import MemoryBackend

locks = Locks(MemoryBackend())


def build_report() -> None: ...  # the work of yours that one process at a time may do


with locks.lock("report", ttl=30):
    build_report()


# --8<-- [end:show]
