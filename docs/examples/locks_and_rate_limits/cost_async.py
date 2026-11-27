# --8<-- [start:show]
from pashe import AsyncRateLimiter
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import SlidingWindow

limiter = AsyncRateLimiter(AsyncMemoryBackend())
searches = SlidingWindow.per_minute(100)


async def search(user_id: int, query: str, *, exact: bool) -> list[str]:
    await limiter.count(f"user:{user_id}", searches, cost=5 if exact else 1)  # exact: five calls
    return [query]  # the search of yours


# --8<-- [end:show]
async def main() -> None:
    await search(1, "kettle", exact=True)
