# --8<-- [start:show]
from pashe import AsyncLocks
from pashe.backends import AsyncMemoryBackend

locks = AsyncLocks(AsyncMemoryBackend())


async def build_report() -> None: ...  # the work of yours that one process at a time may do


async def main() -> None:
    lock = await locks.try_lock("report", ttl=30)  # the lock if it is free now, else None
    if lock is not None:
        async with lock:
            await build_report()


# --8<-- [end:show]
