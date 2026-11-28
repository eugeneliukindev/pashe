# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncRateLimiter
from pashe.backends import AsyncSQLiteBackend
from pashe.ratelimit import SlidingWindow

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = AsyncRateLimiter(backend)

api = SlidingWindow(calls=100, per=60)  # about 100 calls in any 60 seconds
same = SlidingWindow.per_minute(100)  # also per_second and per_hour


async def main() -> None:
    await limiter.count("ip:203.0.113.7", api)  # RateLimitedError over the limit


# --8<-- [end:show]
