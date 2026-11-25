# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


async def build_report() -> None: ...  # the work of yours that one process at a time may do


@cache.locked(ttl=30, key="report:{report_id}")  # every call under the lock of its key
async def build(report_id: int) -> None: ...  # the work of yours for report_id


async def main() -> None:
    lock = await cache.try_lock("report", ttl=30)  # the lock if it is free now, else None
    if lock is not None:
        async with lock:
            await build_report()


# --8<-- [end:show]
