# --8<-- [start:show]
from datetime import timedelta
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stale

cache = Cache(MemoryBackend())


class Rates(TypedDict):
    id: int


@cache(ttl=60, stale=Stale(if_error=timedelta(minutes=10), if_error_on=(ConnectionError, TimeoutError)))
def get_rates() -> Rates:

    # --8<-- [end:show]
    return Rates(id=1)  # what the partner answers
