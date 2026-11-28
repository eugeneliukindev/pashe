# ruff: noqa: ARG001 - partner_id names the key of the limit, not the query
# --8<-- [start:imports]
from datetime import timedelta

from pashe.ratelimit import FixedWindow, SlidingWindow

# --8<-- [end:imports]
from examples.shop.data_async import db, start
from examples.shop.shop_async import Product, limiter, locks

# --8<-- [start:show]
LOGINS = FixedWindow(calls=5, per=900, ban_for=3_600)  # 5 failures in 15 minutes: an hour of ban


async def failed_login(email: str) -> None:
    await limiter.count(f"login:{email}", LOGINS, fail_open=False)  # raises RateLimitedError


@limiter.limited(SlidingWindow.per_minute(100), key="partner:{partner_id}")
async def search_catalogue(partner_id: str, query: str) -> list[Product]:
    rows = await db.execute_fetchall("SELECT * FROM products WHERE name LIKE ?", (f"%{query}%",))
    return [Product(*row) for row in rows]


async def nightly_export() -> None:
    lock = await locks.try_lock("job:nightly-export", ttl=timedelta(minutes=10))
    if lock is None:
        return  # another server runs it
    async with lock:
        ...  # export the orders of the day


# --8<-- [end:show]
async def main() -> None:
    await start()  # opens the database of the shop
    # --8<-- [start:calls]
    await failed_login("ada@example.com")
    await search_catalogue("acme", "coffee")
    await nightly_export()
    # --8<-- [end:calls]
