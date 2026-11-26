# --8<-- [start:show]
from pashe import Locks
from pashe.backends import MemoryBackend

locks = Locks(MemoryBackend())


def build_report() -> None: ...  # the work of yours that one process at a time may do


lock = locks.try_lock("report", ttl=30)  # the lock if it is free now, else None
if lock is not None:
    with lock:
        build_report()


@locks.locked(ttl=30, key="report:{report_id}")  # every call under the lock of its key
def build(report_id: int) -> None: ...  # the work of yours for report_id


# --8<-- [end:show]
