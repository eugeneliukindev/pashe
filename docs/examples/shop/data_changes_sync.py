# --8<-- [start:imports]
from dataclasses import replace

# --8<-- [end:imports]
from examples.shop.data_sync import db
from examples.shop.shop_sync import Product, cache
from examples.shop.slow_query_sync import get_product


# --8<-- [start:show]
@cache(ttl=600, key="category:{category}", tags=["category:{category}"])
def list_category(category: str) -> list[Product]:
    rows = db.execute("SELECT * FROM products WHERE category = ?", (category,)).fetchall()
    return [Product(*row) for row in rows]


def change_price(product: Product, price_cents: int) -> None:
    db.execute("UPDATE products SET price_cents = ? WHERE id = ?", (price_cents, product.id))
    db.commit()  # first: a read between an invalidation and the commit would store the old price
    get_product.set(replace(product, price_cents=price_cents), product.id)
    cache.invalidate_tags(f"category:{product.category}")


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    change_price(get_product(1), 990)
    # --8<-- [end:calls]
