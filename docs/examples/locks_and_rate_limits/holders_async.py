# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


@cache.locked(ttl=60, holders=3)  # at most three exports at once, in every process
async def export(tenant: str) -> None: ...  # the work of yours that a few may do together


async def main() -> None:
    async with cache.lock("reports", ttl=60, holders=3):  # the same for a block
        await export("acme")


# --8<-- [end:show]
