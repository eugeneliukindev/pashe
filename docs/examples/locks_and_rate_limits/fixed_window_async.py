# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncRateLimiter
from pashe.backends import AsyncSQLiteBackend
from pashe.ratelimit import FixedWindow

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = AsyncRateLimiter(backend)

logins = FixedWindow(calls=5, per=60, ban_for=300)  # the 6th call bans for 5 min
same = FixedWindow.per_minute(5, ban_for=300)  # also per_second and per_hour


async def main() -> None:
    await limiter.count("login:ada@example.com", logins)  # RateLimitedError over the limit, or banned


# --8<-- [end:show]
