# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncRateLimiter
from pashe.backends import AsyncSQLiteBackend
from pashe.ratelimit import FixedWindow

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = AsyncRateLimiter(backend)
logins = FixedWindow(calls=5, per=900, ban_for=3600)  # 5 failures in 15 minutes: an hour of ban


async def failed_login(email: str) -> None:
    await limiter.count(f"login:{email}", logins, fail_open=False)  # a failing backend raises BackendError


# --8<-- [end:show]
async def main() -> None:
    await failed_login("ada@example.com")
