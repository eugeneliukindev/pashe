# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stampede

cache = AsyncCache(AsyncMemoryBackend())


class Prices(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(revalidate_before=10))
async def get_prices() -> Prices:
    return Prices(id=1)  # your slow query


# --8<-- [end:show]
