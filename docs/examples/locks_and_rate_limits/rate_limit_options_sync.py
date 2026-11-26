# ruff: noqa: F841 - the page shows how to read what is left of the limit
# --8<-- [start:show]
from pashe import RateLimiter
from pashe.backends import MemoryBackend
from pashe.ratelimit import FixedWindow, SlidingWindow

limiter = RateLimiter(MemoryBackend())

exports = SlidingWindow(
    calls=10,  # calls that pass
    per=60,  # in any span of this many seconds
)
logins = FixedWindow(
    calls=5,  # calls that pass
    per=60,  # per window of this many seconds
    ban_for=300,  # the ban once over it; None: per
)


@limiter.limited(
    exports,  # the limit
    key="user:{user_id}",  # a template; None: one per function
)
def export(user_id: int) -> None: ...


def main() -> None:
    state = limiter.count(
        "login:ada@example.com",  # what the limit counts
        logins,  # the limit
        cost=1,  # how many calls this one counts as
        fail_open=True,  # let calls through a failing backend
    )  # RateLimitedError over the limit
    if state is not None:  # None: the backend failed
        # what is left of the limit, for RateLimit headers
        limit, left, resets_in = state.limit, state.remaining, state.reset_after
    export(1)


# --8<-- [end:show]
