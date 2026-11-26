"""Rate limits: the windows a limit counts calls in, and what a limit tells about a counted call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

from pashe._internal.checks import expect_positive, expect_type

__all__ = ["FixedWindow", "Limit", "RateLimitState", "SlidingWindow", "per_hour", "per_minute", "per_second"]


type Limit = SlidingWindow | FixedWindow
"""A limit: a SlidingWindow or a FixedWindow."""

_MINUTE: Final = 60.0
_HOUR: Final = 3600.0


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class SlidingWindow:
    """Allows about ``calls`` calls in any span of ``per`` seconds, counted in the backend.

    It keeps two counters per key, for the current and the last fixed window, and weighs the last
    one by how much of it still falls inside the sliding window. Refused calls are not counted.

    Attributes:
        calls: how many calls the window allows.
        per: the span of the window in seconds.

    Examples:
        >>> from pashe.ratelimit import SlidingWindow
        >>> SlidingWindow(calls=100, per=60)
        SlidingWindow(calls=100, per=60)
    """

    calls: int
    per: float

    def __post_init__(self) -> None:
        """Check the limit.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: calls or per is not positive.
        """
        expect_positive("SlidingWindow.calls", self.calls, "how many calls the window allows, 1 or more", kind=int)
        expect_positive("SlidingWindow.per", self.per, "the span of the window, more than 0 seconds")


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class FixedWindow:
    """Allows ``calls`` calls per window of ``per`` seconds that starts with the first call.

    The first call over the limit blocks the key for ``ban_for`` seconds.

    Attributes:
        calls: how many calls the window allows.
        per: the length of the window in seconds.
        ban_for: how long the first call over the limit blocks the key; None means ``per``.

    Examples:
        >>> from pashe.ratelimit import FixedWindow
        >>> FixedWindow(calls=5, per=60, ban_for=300)
        FixedWindow(calls=5, per=60, ban_for=300)
    """

    calls: int
    per: float
    ban_for: float | None = None

    def __post_init__(self) -> None:
        """Check the limit.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: calls, per or ban_for is not positive.
        """
        expect_positive("FixedWindow.calls", self.calls, "how many calls the window allows, 1 or more", kind=int)
        expect_positive("FixedWindow.per", self.per, "the length of the window, more than 0 seconds")
        if self.ban_for is not None:
            expect_positive(
                "FixedWindow.ban_for", self.ban_for, "more than 0 seconds, or None for the length of the window"
            )

    @property
    def ban_seconds(self) -> float:
        """How long the first call over the limit blocks the key."""
        return self.ban_for or self.per  # ban_for is positive, or None


def per_second(calls: int, /) -> SlidingWindow:
    """Allow calls in any second.

    Args:
        calls: how many calls the window allows.

    Returns:
        A sliding window of one second.

    Raises:
        InvalidOptionsError: calls is not positive.

    Examples:
        >>> from pashe.ratelimit import per_second
        >>> per_second(100)
        SlidingWindow(calls=100, per=1)
    """
    expect_type("calls", calls, int)
    return SlidingWindow(calls=calls, per=1)


def per_minute(calls: int, /) -> SlidingWindow:
    """Allow calls in any minute.

    Args:
        calls: how many calls the window allows.

    Returns:
        A sliding window of one minute.

    Raises:
        InvalidOptionsError: calls is not positive.

    Examples:
        >>> from pashe.ratelimit import per_minute
        >>> per_minute(100)
        SlidingWindow(calls=100, per=60.0)
    """
    expect_type("calls", calls, int)
    return SlidingWindow(calls=calls, per=_MINUTE)


def per_hour(calls: int, /) -> SlidingWindow:
    """Allow calls in any hour.

    Args:
        calls: how many calls the window allows.

    Returns:
        A sliding window of one hour.

    Raises:
        InvalidOptionsError: calls is not positive.

    Examples:
        >>> from pashe.ratelimit import per_hour
        >>> per_hour(100)
        SlidingWindow(calls=100, per=3600.0)
    """
    expect_type("calls", calls, int)
    return SlidingWindow(calls=calls, per=_HOUR)


@final
@dataclass(frozen=True, slots=True)
class RateLimitState:
    """What is left of a limit after a counted call, for headers such as ``RateLimit``.

    Attributes:
        limit: how many calls the limit allows per window.
        remaining: how many more calls of cost 1 pass now.
        reset_after: seconds until the current window ends: of a FixedWindow, its counter; of
            a SlidingWindow, the fixed window it counts in.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.ratelimit import FixedWindow
        >>> state = Cache(MemoryBackend()).rate_limit("login:ada", FixedWindow(calls=5, per=60))
        >>> state.limit, state.remaining
        (5, 4)
    """

    limit: int
    remaining: int
    reset_after: float
