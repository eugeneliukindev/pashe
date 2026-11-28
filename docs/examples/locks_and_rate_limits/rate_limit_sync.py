# ruff: noqa: F841 - the page shows how to read what is left of the limit
# --8<-- [start:show]
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pashe import RateLimiter
from pashe.backends import SQLiteBackend
from pashe.ratelimit import SlidingWindow

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = RateLimiter(backend)
ip = "203.0.113.7"  # the address of the client


@dataclass
class Export:
    user_id: int


@limiter.limited(SlidingWindow.per_minute(10), key="user:{user_id}")
def export(user_id: int) -> Export:
    return Export(user_id)  # the heavy work of yours


def main() -> None:
    state = limiter.count(f"ip:{ip}", SlidingWindow.per_minute(100))  # raises RateLimitedError over it
    if state is not None:  # None when the backend fails and the call went through uncounted
        left, resets_in = state.remaining, state.reset_after


# --8<-- [end:show]
