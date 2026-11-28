# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import RateLimiter
from pashe.backends import SQLiteBackend
from pashe.ratelimit import FixedWindow

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = RateLimiter(backend)
logins = FixedWindow(calls=5, per=900, ban_for=3600)  # 5 failures in 15 minutes: an hour of ban


def failed_login(email: str) -> None:
    limiter.count(f"login:{email}", logins, fail_open=False)  # a failing backend raises BackendError


# --8<-- [end:show]
def main() -> None:
    failed_login("ada@example.com")
