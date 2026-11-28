# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Store

cache = Cache(MemoryBackend())


class Product(TypedDict):
    id: int


@cache(ttl=300, store=Store(slower_than=0.05))  # kept only if its load took 50 ms or more
def get_product(product_id: int) -> Product:
    return Product(id=product_id)  # a query the source answers fast, cheap to repeat


# --8<-- [end:show]
def main() -> None:
    get_product(1)
