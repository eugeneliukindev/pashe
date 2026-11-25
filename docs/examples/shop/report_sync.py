# --8<-- [start:imports]
from pashe.options import Stale, Stampede

# --8<-- [end:imports]
from examples.shop.data_sync import db
from examples.shop.shop_sync import cache

# --8<-- [start:show]
SALES = "SELECT count(*), coalesce(sum(total_cents), 0) FROM orders WHERE day = ?"


@cache(
    ttl=60,
    key="report:sales:{day}",
    stale=Stale(while_revalidate=600),  # the old report answers at once while a new one is built
    stampede=Stampede(
        lock_for=30,  # one process of the service builds it, the others wait for it
        max_concurrent_loads=2,  # at most two reports build at once in a process
    ),
)
def sales_report(day: str) -> dict[str, int]:
    orders, revenue_cents = db.execute(SALES, (day,)).fetchone()
    return {"orders": orders, "revenue_cents": revenue_cents}


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    sales_report("2026-11-21")
    # --8<-- [end:calls]
