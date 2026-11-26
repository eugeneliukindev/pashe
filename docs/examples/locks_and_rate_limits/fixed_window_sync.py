# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.ratelimit import FixedWindow

cache = Cache(MemoryBackend())

logins = FixedWindow(calls=5, per=60, ban_for=300)  # 5 a window from the first call; the 6th bans for 5 min
same = FixedWindow.per_minute(5, ban_for=300)  # also per_second and per_hour


def main() -> None:
    cache.rate_limit("login:ada@example.com", logins)  # RateLimitedError over the limit, or banned


# --8<-- [end:show]
