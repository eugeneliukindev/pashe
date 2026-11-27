# --8<-- [start:show]
from pashe import AsyncRateLimiter
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import FixedWindow

limiter = AsyncRateLimiter(AsyncMemoryBackend())
logins = FixedWindow(calls=5, per=900, ban_for=3600)  # 5 failures in 15 minutes: an hour of ban


async def failed_login(email: str) -> None:
    await limiter.count(f"login:{email}", logins, fail_open=False)  # a failing backend raises BackendError


# --8<-- [end:show]
async def main() -> None:
    await failed_login("ada@example.com")
