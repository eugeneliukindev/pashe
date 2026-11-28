# --8<-- [start:imports]
from datetime import timedelta

from pashe.options import Stale, Stampede

# --8<-- [end:imports]
from examples.shop.data_async import db, start
from examples.shop.shop_async import cache

# --8<-- [start:show]
SALES = "SELECT count(*), coalesce(sum(total_cents), 0) FROM orders WHERE day = ?"


@cache(
    ttl=60,
    key="report:sales:{day}",
    stale=Stale(while_revalidate=timedelta(minutes=10)),  # the old report answers at once while a new one is built
    stampede=Stampede(
        lock_for=30,  # one process of the service builds it, the others wait for it
        max_loads=2,  # at most two reports build at once in a process
    ),
)
async def sales_report(day: str) -> dict[str, int]:
    cursor = await db.execute(SALES, (day,))
    orders, revenue_cents = await cursor.fetchone() or (0, 0)  # an aggregate always gives a row
    return {"orders": orders, "revenue_cents": revenue_cents}


# --8<-- [end:show]
async def main() -> None:
    await start()  # opens the database of the shop
    # --8<-- [start:calls]
    await sales_report("2026-11-21")
    # --8<-- [end:calls]
