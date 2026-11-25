# --8<-- [start:imports]
from dataclasses import replace

# --8<-- [end:imports]
from examples.shop.data_async import db, start
from examples.shop.shop_async import Product, cache
from examples.shop.slow_query_async import get_product


# --8<-- [start:show]
@cache(ttl=600, key="category:{category}", tags=["category:{category}"])
async def list_category(category: str) -> list[Product]:
    rows = await db.execute_fetchall("SELECT * FROM products WHERE category = ?", (category,))
    return [Product(*row) for row in rows]


async def change_price(product: Product, price_cents: int) -> None:
    await db.execute("UPDATE products SET price_cents = ? WHERE id = ?", (price_cents, product.id))
    await db.commit()  # first: a read between an invalidation and the commit would store the old price
    await get_product.set(replace(product, price_cents=price_cents), product.id)
    await cache.invalidate_tags(f"category:{product.category}")


# --8<-- [end:show]
async def main() -> None:
    await start()  # opens the database of the shop
    # --8<-- [start:calls]
    await change_price(await get_product(1), 990)
    # --8<-- [end:calls]
