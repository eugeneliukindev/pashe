# ruff: noqa: S608 - only placeholders go into the SQL; the ids go as parameters
from examples.shop.data_async import db, start
from examples.shop.shop_async import cache


# --8<-- [start:show]
@cache.batch(ttl=300, key="price:{}")
async def get_prices(product_ids: list[int]) -> dict[int, int]:
    marks = ", ".join("?" * len(product_ids))
    sql = f"SELECT id, price_cents FROM products WHERE id IN ({marks})"
    rows = await db.execute_fetchall(sql, product_ids)
    return {row[0]: row[1] for row in rows}  # id: price_cents


# --8<-- [end:show]
async def main() -> None:
    await start()  # opens the database of the shop
    # --8<-- [start:calls]
    await get_prices([1, 2])  # one query for both
    await get_prices([1, 2, 3])  # a query only for 3
    # --8<-- [end:calls]
