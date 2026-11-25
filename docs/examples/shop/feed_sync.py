# ruff: noqa: S608 - only placeholders go into the SQL; the ids go as parameters
from examples.shop.data_sync import db
from examples.shop.shop_sync import cache


# --8<-- [start:show]
@cache.batch(ttl=300, key="price:{}")
def get_prices(product_ids: list[int]) -> dict[int, int]:
    marks = ", ".join("?" * len(product_ids))
    sql = f"SELECT id, price_cents FROM products WHERE id IN ({marks})"
    return dict(db.execute(sql, product_ids).fetchall())


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_prices([1, 2])  # one query for both
    get_prices([1, 2, 3])  # a query only for 3
    # --8<-- [end:calls]
