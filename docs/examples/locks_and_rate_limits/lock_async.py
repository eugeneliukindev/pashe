# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


async def build_report() -> None: ...  # the work of yours that one process at a time may do


async def main() -> None:
    async with cache.lock("report", ttl=30):
        await build_report()


# --8<-- [end:show]
