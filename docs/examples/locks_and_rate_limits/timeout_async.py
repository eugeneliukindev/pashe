# --8<-- [start:show]
from pashe import AsyncLocks
from pashe.backends import AsyncMemoryBackend
from pashe.errors import LockTimeoutError

locks = AsyncLocks(AsyncMemoryBackend())


async def build_report() -> None: ...  # the work of yours that one process at a time may do


async def nightly_report() -> bool:
    try:
        async with locks.lock("report", ttl=30, timeout=10):  # wait at most 10 seconds
            await build_report()
    except LockTimeoutError:
        return False  # held for all 10 seconds: someone else builds it
    return True


# --8<-- [end:show]
async def main() -> None:
    await nightly_report()
