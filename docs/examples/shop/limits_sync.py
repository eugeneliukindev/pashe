# ruff: noqa: ARG001 - partner_id names the key of the limit, not the query
# --8<-- [start:imports]
from pashe.ratelimit import FixedWindow, SlidingWindow

# --8<-- [end:imports]
from examples.shop.data_sync import db
from examples.shop.shop_sync import Product, cache

# --8<-- [start:show]
LOGINS = FixedWindow(calls=5, per=900, ban_for=3_600)  # 5 failures in 15 minutes: an hour of ban


def failed_login(email: str) -> None:
    cache.rate_limit(f"login:{email}", LOGINS, fail_open=False)  # raises RateLimitedError


@cache.rate_limited(SlidingWindow.per_minute(100), key="partner:{partner_id}")
def search_catalogue(partner_id: str, query: str) -> list[Product]:
    rows = db.execute("SELECT * FROM products WHERE name LIKE ?", (f"%{query}%",)).fetchall()
    return [Product(*row) for row in rows]


def nightly_export() -> None:
    lock = cache.try_lock("job:nightly-export", ttl=600)
    if lock is None:
        return  # another server runs it
    with lock:
        ...  # export the orders of the day


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    failed_login("ada@example.com")
    search_catalogue("acme", "coffee")
    nightly_export()
    # --8<-- [end:calls]
