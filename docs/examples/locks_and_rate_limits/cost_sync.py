# --8<-- [start:show]
from pashe import RateLimiter
from pashe.backends import MemoryBackend
from pashe.ratelimit import SlidingWindow

limiter = RateLimiter(MemoryBackend())
searches = SlidingWindow.per_minute(100)


def search(user_id: int, query: str, *, exact: bool) -> list[str]:
    limiter.count(f"user:{user_id}", searches, cost=5 if exact else 1)  # exact: five calls
    return [query]  # the search of yours


# --8<-- [end:show]
def main() -> None:
    search(1, "kettle", exact=True)
