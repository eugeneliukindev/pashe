# --8<-- [start:show]
from pashe import RateLimiter
from pashe.backends import MemoryBackend
from pashe.ratelimit import FixedWindow

limiter = RateLimiter(MemoryBackend())
logins = FixedWindow(calls=5, per=900, ban_for=3600)  # 5 failures in 15 minutes: an hour of ban


def failed_login(email: str) -> None:
    limiter.count(f"login:{email}", logins, fail_open=False)  # a failing backend raises BackendError


# --8<-- [end:show]
def main() -> None:
    failed_login("ada@example.com")
