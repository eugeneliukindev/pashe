# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import RateLimiter
from pashe.backends import SQLiteBackend
from pashe.ratelimit import FixedWindow

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = RateLimiter(backend)

logins = FixedWindow(calls=5, per=60, ban_for=300)  # the 6th call bans for 5 min
same = FixedWindow.per_minute(5, ban_for=300)  # also per_second and per_hour


def main() -> None:
    limiter.count("login:ada@example.com", logins)  # RateLimitedError over the limit, or banned


# --8<-- [end:show]
