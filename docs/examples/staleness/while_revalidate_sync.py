# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stale

cache = Cache(MemoryBackend())


class Prices(TypedDict):
    id: int


@cache(ttl=60, stale=Stale(while_revalidate=30))
def get_prices() -> Prices:

    # --8<-- [end:show]
    return Prices(id=1)  # your slow query
