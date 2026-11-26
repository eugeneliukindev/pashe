# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache.locked(
    ttl=30,  # how long the lock lives without an extension, in seconds or a timedelta
    key="report:{report_id}",  # a template over the arguments; None, the default: one lock for the function
    timeout=None,  # the most a call waits for the lock, then LockTimeoutError; None waits as long as it takes
    holders=1,  # how many calls run at once, in every process over the backend
)
def build(report_id: int) -> None: ...


def main() -> None:
    with cache.lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked
        timeout=10,  # as in locked
        holders=1,  # as in locked
    ):
        build(1)

    lock = cache.try_lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked; try_lock waits for nothing, so it takes no timeout
        holders=1,  # as in locked
    )
    if lock is not None:  # None: as many as holders hold it now
        with lock:
            build(1)


# --8<-- [end:show]
