# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncLocks
from pashe.backends import AsyncSQLiteBackend

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = AsyncLocks(backend)


@locks.locked(
    ttl=30,  # the lock lives this long unextended
    key="report:{report_id}",  # a template; None: one per function
    timeout=None,  # the longest wait; None: forever
    holders=1,  # how many hold it at once
)
async def build(report_id: int) -> None: ...


async def main() -> None:
    async with locks.lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked
        timeout=10,  # as in locked
        holders=1,  # as in locked
    ):
        await build(1)

    lock = await locks.try_lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked; no wait, no timeout
        holders=1,  # as in locked
    )
    if lock is not None:  # None: it is taken
        async with lock:
            await build(1)


# --8<-- [end:show]
