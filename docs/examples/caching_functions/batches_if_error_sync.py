# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stale

cache = Cache(MemoryBackend())


class Price(TypedDict):
    cents: int


@cache.batch(ttl=60, key="price:{}", stale=Stale(if_error=600, if_error_on=(ConnectionError,)))
def get_prices(product_ids: list[int]) -> dict[int, Price]:
    return {product_id: Price(cents=100) for product_id in product_ids}  # your price service


# --8<-- [end:show]
def main() -> None:
    get_prices([1, 2])
