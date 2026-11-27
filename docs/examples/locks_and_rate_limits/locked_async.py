# --8<-- [start:show]
from pashe import AsyncLocks
from pashe.backends import AsyncMemoryBackend

locks = AsyncLocks(AsyncMemoryBackend())


@locks.locked(ttl=30, key="report:{report_id}")  # every call under the lock of its key
async def build(report_id: int) -> None: ...  # the work of yours for report_id


# --8<-- [end:show]
async def main() -> None:
    await build(1)
