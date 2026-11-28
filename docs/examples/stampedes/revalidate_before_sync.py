# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede

cache = Cache(MemoryBackend())


class Prices(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(revalidate_before=10))
def get_prices() -> Prices:
    return Prices(id=1)  # your slow query


# --8<-- [end:show]
