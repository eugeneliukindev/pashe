# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stale

cache = AsyncCache(AsyncMemoryBackend())


class Price(TypedDict):
    cents: int


@cache.batch(ttl=60, key="price:{}", stale=Stale(if_error=600, if_error_on=(ConnectionError,)))
async def get_prices(product_ids: list[int]) -> dict[int, Price]:
    return {product_id: Price(cents=100) for product_id in product_ids}  # your price service


# --8<-- [end:show]
async def main() -> None:
    await get_prices([1, 2])
