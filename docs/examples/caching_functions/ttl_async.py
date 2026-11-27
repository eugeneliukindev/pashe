# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


class Rates(TypedDict):
    id: int


@cache(ttl=60)  # fresh for 60 seconds, then the next call reloads it
async def get_rates() -> Rates:
    return Rates(id=1)  # what the partner answers


# --8<-- [end:show]
async def main() -> None:
    await get_rates()
