# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


class Rates(TypedDict):
    id: int


@cache(ttl=60)  # fresh for 60 seconds, then the next call reloads it
def get_rates() -> Rates:
    return Rates(id=1)  # what the partner answers


# --8<-- [end:show]
def main() -> None:
    get_rates()
