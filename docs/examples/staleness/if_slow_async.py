# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stale

cache = AsyncCache(AsyncMemoryBackend())


class Feed(TypedDict):
    id: int


@cache(ttl=60, stale=Stale(if_slow=300, slow_after=0.2))
async def get_feed() -> Feed:

    # --8<-- [end:show]
    return Feed(id=1)  # your slow query
