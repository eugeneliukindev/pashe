# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import IfSlow, Stale

cache = Cache(MemoryBackend())


class Feed(TypedDict):
    id: int


@cache(ttl=60, stale=Stale(if_slow=IfSlow(300, after=0.2)))
def get_feed() -> Feed:

    # --8<-- [end:show]
    return Feed(id=1)  # your slow query
