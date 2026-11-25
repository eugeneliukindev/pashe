# ruff: noqa: F841 - the page shows how to read what is left of the limit
# --8<-- [start:show]
from dataclasses import dataclass

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import per_minute

cache = AsyncCache(AsyncMemoryBackend())
ip = "203.0.113.7"  # the address of the client


@dataclass
class Export:
    user_id: int


@cache.rate_limited(per_minute(10), key="user:{user_id}")
async def export(user_id: int) -> Export:
    return Export(user_id)  # the heavy work of yours


async def main() -> None:
    state = await cache.rate_limit(f"ip:{ip}", per_minute(100))  # raises RateLimitedError over it
    if state is not None:  # None when the backend fails and the call went through uncounted
        left, resets_in = state.remaining, state.reset_after


# --8<-- [end:show]
