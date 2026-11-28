# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede

cache = Cache(MemoryBackend())


class Product(TypedDict):
    id: int


@cache(ttl=60)  # share_loads is on by default
def get_product(product_id: int) -> Product:
    return Product(id=product_id)  # your query


@cache(ttl=60, stampede=Stampede(share_loads=False))  # every call loads on its own
def get_quote(product_id: int) -> Product:
    return Product(id=product_id)  # a result each caller changes


# --8<-- [end:show]
def main() -> None:
    get_product(1)
    get_quote(1)
