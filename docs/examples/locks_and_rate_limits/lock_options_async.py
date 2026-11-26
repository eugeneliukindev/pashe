# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


@cache.locked(
    ttl=30,  # the lock lives this long unextended
    key="report:{report_id}",  # a template; None: one per function
    timeout=None,  # the longest wait; None: forever
    holders=1,  # how many hold it at once
)
async def build(report_id: int) -> None: ...


async def main() -> None:
    async with cache.lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked
        timeout=10,  # as in locked
        holders=1,  # as in locked
    ):
        await build(1)

    lock = await cache.try_lock(
        "nightly-export",  # the name of the lock
        ttl=30,  # as in locked; no wait, no timeout
        holders=1,  # as in locked
    )
    if lock is not None:  # None: it is taken
        async with lock:
            await build(1)


# --8<-- [end:show]
