# --8<-- [start:show]
from pashe import Locks
from pashe.backends import MemoryBackend
from pashe.errors import LockTimeoutError

locks = Locks(MemoryBackend())


def build_report() -> None: ...  # the work of yours that one process at a time may do


def nightly_report() -> bool:
    try:
        with locks.lock("report", ttl=30, timeout=10):  # wait at most 10 seconds
            build_report()
    except LockTimeoutError:
        return False  # held for all 10 seconds: someone else builds it
    return True


# --8<-- [end:show]
def main() -> None:
    nightly_report()
