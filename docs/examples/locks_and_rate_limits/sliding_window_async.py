# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import SlidingWindow

cache = AsyncCache(AsyncMemoryBackend())

api = SlidingWindow(calls=100, per=60)  # about 100 calls in any 60 seconds
same = SlidingWindow.per_minute(100)  # also per_second and per_hour


async def main() -> None:
    await cache.rate_limit("ip:203.0.113.7", api)  # RateLimitedError over the limit


# --8<-- [end:show]
