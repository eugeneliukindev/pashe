# ruff: noqa: F841 - the page shows how to read what is left of the limit
# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.ratelimit import FixedWindow, SlidingWindow

cache = Cache(MemoryBackend())

exports = SlidingWindow(
    calls=10,  # how many calls pass in any span of per
    per=60,  # the span, in seconds
)
logins = FixedWindow(
    calls=5,  # how many calls pass in a window that starts with the first call
    per=60,  # the length of the window, in seconds
    ban_for=300,  # how long the first call over it blocks the key; None, the default: per
)


@cache.rate_limited(
    exports,  # the limit
    key="user:{user_id}",  # a template over the arguments; None, the default: one limit for the function
)
def export(user_id: int) -> None: ...


def main() -> None:
    state = cache.rate_limit(
        "login:ada@example.com",  # what the limit counts
        logins,  # the limit
        cost=1,  # how many calls this one counts as, such as 5 for a heavy one
        fail_open=True,  # a failing backend lets the call through uncounted; False raises BackendError
    )  # RateLimitedError over the limit
    if state is not None:  # None when the backend failed and the call went through uncounted
        limit, left, resets_in = state.limit, state.remaining, state.reset_after  # for headers such as RateLimit
    export(1)


# --8<-- [end:show]
