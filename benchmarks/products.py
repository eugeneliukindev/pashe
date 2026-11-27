"""What the benchmarks of the codecs and the compressors store: a page of a shop, as many products as asked."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final

# a small entry, a page or a list, and a big report: the largest value worth caching
COUNTS: Final = (1, 100, 10_000)


@dataclass
class Product:
    id: int
    name: str
    category: str
    price_cents: int
    in_stock: bool
    tags: list[str]


def products(count: int) -> list[Product]:
    return [
        Product(
            id=number,
            name=f"Coffee beans {number}",
            category="coffee",
            price_cents=1290 + number,
            in_stock=number % 3 != 0,
            tags=["arabica", "250 g"],
        )
        for number in range(count)
    ]


def product_dicts(count: int) -> list[dict[str, Any]]:
    """The products as a codec of plain JSON gives them back."""
    return [asdict(product) for product in products(count)]
