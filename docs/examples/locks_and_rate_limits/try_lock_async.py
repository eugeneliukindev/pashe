# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncLocks
from pashe.backends import AsyncSQLiteBackend

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = AsyncLocks(backend)


async def build_report() -> None: ...  # the work of yours that one process at a time may do


async def main() -> None:
    lock = await locks.try_lock("report", ttl=30)  # the lock if it is free now, else None
    if lock is not None:
        async with lock:
            await build_report()


# --8<-- [end:show]
