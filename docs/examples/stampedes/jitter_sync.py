# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede

cache = Cache(MemoryBackend())


class Product(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(jitter=0.1))  # an entry lives 54 to 66 s
def list_products(category_id: int) -> Product:
    return Product(id=category_id)  # many entries stored together, as after a deploy


# --8<-- [end:show]
def main() -> None:
    list_products(1)
