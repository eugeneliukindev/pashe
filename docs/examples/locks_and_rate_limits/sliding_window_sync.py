# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import RateLimiter
from pashe.backends import SQLiteBackend
from pashe.ratelimit import SlidingWindow

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = RateLimiter(backend)

api = SlidingWindow(calls=100, per=60)  # about 100 calls in any 60 seconds
same = SlidingWindow.per_minute(100)  # also per_second and per_hour


def main() -> None:
    limiter.count("ip:203.0.113.7", api)  # RateLimitedError over the limit


# --8<-- [end:show]
