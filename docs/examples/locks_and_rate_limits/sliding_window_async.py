# --8<-- [start:show]
from pashe import AsyncRateLimiter
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import SlidingWindow

limiter = AsyncRateLimiter(AsyncMemoryBackend())

api = SlidingWindow(calls=100, per=60)  # about 100 calls in any 60 seconds
same = SlidingWindow.per_minute(100)  # also per_second and per_hour


async def main() -> None:
    await limiter.count("ip:203.0.113.7", api)  # RateLimitedError over the limit


# --8<-- [end:show]
