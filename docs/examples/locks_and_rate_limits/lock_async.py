# --8<-- [start:show]
from pashe import AsyncLocks
from pashe.backends import AsyncMemoryBackend

locks = AsyncLocks(AsyncMemoryBackend())


async def build_report() -> None: ...  # the work of yours that one process at a time may do


async def main() -> None:
    async with locks.lock("report", ttl=30):
        await build_report()


# --8<-- [end:show]
