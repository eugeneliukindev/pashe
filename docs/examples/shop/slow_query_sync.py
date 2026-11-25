from examples.shop.data_sync import db
from examples.shop.shop_sync import Product, cache


# --8<-- [start:show]
@cache(ttl=300, key="product:{product_id}")
def get_product(product_id: int) -> Product:
    row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise LookupError(product_id)
    return Product(*row)


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_product(1)  # reads the database and stores the product
    get_product(1)  # answered from the cache
    # --8<-- [end:calls]
