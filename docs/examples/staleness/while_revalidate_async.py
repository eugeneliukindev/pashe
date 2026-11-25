# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stale

cache = AsyncCache(AsyncMemoryBackend())


class Prices(TypedDict):
    id: int


@cache(ttl=60, stale=Stale(while_revalidate=30))
async def get_prices() -> Prices:

    # --8<-- [end:show]
    return Prices(id=1)  # your slow query
