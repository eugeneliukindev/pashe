# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stampede

cache = AsyncCache(AsyncMemoryBackend())


class Product(TypedDict):
    id: int


@cache(ttl=60)  # share_loads is on by default
async def get_product(product_id: int) -> Product:
    return Product(id=product_id)  # your query


@cache(ttl=60, stampede=Stampede(share_loads=False))  # every call loads on its own
async def get_quote(product_id: int) -> Product:
    return Product(id=product_id)  # a result each caller changes


# --8<-- [end:show]
async def main() -> None:
    await get_product(1)
    await get_quote(1)
