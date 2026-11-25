from examples.shop.data_async import db, start
from examples.shop.shop_async import Product, cache


# --8<-- [start:show]
@cache(ttl=300, key="product:{product_id}")
async def get_product(product_id: int) -> Product:
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = await cursor.fetchone()
    if row is None:
        raise LookupError(product_id)
    return Product(*row)


# --8<-- [end:show]
async def main() -> None:
    await start()  # opens the database of the shop
    # --8<-- [start:calls]
    await get_product(1)  # reads the database and stores the product
    await get_product(1)  # answered from the cache
    # --8<-- [end:calls]
