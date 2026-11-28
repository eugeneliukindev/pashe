# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncRateLimiter
from pashe.backends import AsyncSQLiteBackend
from pashe.ratelimit import SlidingWindow

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = AsyncRateLimiter(backend)
searches = SlidingWindow.per_minute(100)


async def search(user_id: int, query: str, *, exact: bool) -> list[str]:
    await limiter.count(f"user:{user_id}", searches, cost=5 if exact else 1)  # exact: five calls
    return [query]  # the search of yours


# --8<-- [end:show]
async def main() -> None:
    await search(1, "kettle", exact=True)
