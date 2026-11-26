# --8<-- [start:show]
from pashe import Locks
from pashe.backends import MemoryBackend

locks = Locks(MemoryBackend())


@locks.locked(
    ttl=30,  # the lock lives this long unextended
    key="report:{report_id}",  # a template; None: one per function
    timeout=None,  # the longest wait; None: forever
    holders=1,  # how many hold it at once
)
def build(report_id: int) -> None: ...


def main() -> None:
    with locks.lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked
        timeout=10,  # as in locked
        holders=1,  # as in locked
    ):
        build(1)

    lock = locks.try_lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked; no wait, no timeout
        holders=1,  # as in locked
    )
    if lock is not None:  # None: it is taken
        with lock:
            build(1)


# --8<-- [end:show]
