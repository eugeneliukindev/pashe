# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stampede

cache = AsyncCache(AsyncMemoryBackend())


class Product(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(jitter=0.1))  # an entry lives 54 to 66 s
async def list_products(category_id: int) -> Product:
    return Product(id=category_id)  # many entries stored together, as after a deploy


# --8<-- [end:show]
async def main() -> None:
    await list_products(1)
