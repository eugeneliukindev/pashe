# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import IfError, Stale

cache = AsyncCache(AsyncMemoryBackend())


class Rates(TypedDict):
    id: int


@cache(ttl=60, stale=Stale(if_error=IfError(600, on=(ConnectionError, TimeoutError))))
async def get_rates() -> Rates:

    # --8<-- [end:show]
    return Rates(id=1)  # what the partner answers
