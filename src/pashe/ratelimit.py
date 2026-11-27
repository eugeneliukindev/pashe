"""Rate limits: the windows a limit counts calls in, and what a limit tells about a counted call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Self, final

from pashe._internal.checks import parse_int, validate_positive

__all__ = ["FixedWindow", "Limit", "RateLimitState", "SlidingWindow"]

_MINUTE: Final = 60.0
_HOUR: Final = 3600.0


type Limit = SlidingWindow | FixedWindow
"""A limit: a SlidingWindow or a FixedWindow."""


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
        parse_int("SlidingWindow.calls", self.calls, low=1, meaning="how many calls the window allows, 1 or more")
        validate_positive("SlidingWindow.per", self.per, "the span of the window, more than 0 seconds")

    @classmethod
    def per_second(cls, calls: int, /) -> Self:
        """Allow ``calls`` calls in any second.

        Args:
            calls: how many calls the window allows.

        Returns:
            A sliding window of one second.

        Raises:
            TypeError: calls is not an int.
            InvalidOptionsError: calls is not positive.

        Examples:
            >>> from pashe.ratelimit import SlidingWindow
            >>> SlidingWindow.per_second(100)
            SlidingWindow(calls=100, per=1)
        """
        return cls(calls=calls, per=1)

    @classmethod
    def per_minute(cls, calls: int, /) -> Self:
        """Allow ``calls`` calls in any minute.

        Args:
            calls: how many calls the window allows.

        Returns:
            A sliding window of one minute.

        Raises:
            TypeError: calls is not an int.
            InvalidOptionsError: calls is not positive.

        Examples:
            >>> from pashe.ratelimit import SlidingWindow
            >>> SlidingWindow.per_minute(100)
            SlidingWindow(calls=100, per=60.0)
        """
        return cls(calls=calls, per=_MINUTE)

    @classmethod
    def per_hour(cls, calls: int, /) -> Self:
        """Allow ``calls`` calls in any hour.

        Args:
            calls: how many calls the window allows.

        Returns:
            A sliding window of one hour.

        Raises:
            TypeError: calls is not an int.
            InvalidOptionsError: calls is not positive.

        Examples:
            >>> from pashe.ratelimit import SlidingWindow
            >>> SlidingWindow.per_hour(100)
            SlidingWindow(calls=100, per=3600.0)
        """
        return cls(calls=calls, per=_HOUR)


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
        parse_int("FixedWindow.calls", self.calls, low=1, meaning="how many calls the window allows, 1 or more")
        validate_positive("FixedWindow.per", self.per, "the length of the window, more than 0 seconds")
        if self.ban_for is not None:
            validate_positive(
                "FixedWindow.ban_for", self.ban_for, "more than 0 seconds, or None for the length of the window"
            )

    @property
    def ban_seconds(self) -> float:
        """How long the first call over the limit blocks the key."""
        return self.ban_for or self.per  # ban_for is positive, or None

    @classmethod
    def per_second(cls, calls: int, /, *, ban_for: float | None = None) -> Self:
        """Allow ``calls`` calls per window of one second.

        Args:
            calls: how many calls the window allows.
            ban_for: how long the first call over the limit blocks the key; None means the window.

        Returns:
            A fixed window of one second.

        Raises:
            TypeError: calls is not an int.
            InvalidOptionsError: calls or ban_for is not positive.

        Examples:
            >>> from pashe.ratelimit import FixedWindow
            >>> FixedWindow.per_second(5, ban_for=300)
            FixedWindow(calls=5, per=1, ban_for=300)
        """
        return cls(calls=calls, per=1, ban_for=ban_for)

    @classmethod
    def per_minute(cls, calls: int, /, *, ban_for: float | None = None) -> Self:
        """Allow ``calls`` calls per window of one minute.

        Args:
            calls: how many calls the window allows.
            ban_for: how long the first call over the limit blocks the key; None means the window.

        Returns:
            A fixed window of one minute.

        Raises:
            TypeError: calls is not an int.
            InvalidOptionsError: calls or ban_for is not positive.

        Examples:
            >>> from pashe.ratelimit import FixedWindow
            >>> FixedWindow.per_minute(5, ban_for=300)
            FixedWindow(calls=5, per=60.0, ban_for=300)
        """
        return cls(calls=calls, per=_MINUTE, ban_for=ban_for)

    @classmethod
    def per_hour(cls, calls: int, /, *, ban_for: float | None = None) -> Self:
        """Allow ``calls`` calls per window of one hour.

        Args:
            calls: how many calls the window allows.
            ban_for: how long the first call over the limit blocks the key; None means the window.

        Returns:
            A fixed window of one hour.

        Raises:
            TypeError: calls is not an int.
            InvalidOptionsError: calls or ban_for is not positive.

        Examples:
            >>> from pashe.ratelimit import FixedWindow
            >>> FixedWindow.per_hour(5, ban_for=300)
            FixedWindow(calls=5, per=3600.0, ban_for=300)
        """
        return cls(calls=calls, per=_HOUR, ban_for=ban_for)


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
        >>> from pashe import RateLimiter
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.ratelimit import FixedWindow
        >>> state = RateLimiter(MemoryBackend()).count("login:ada", FixedWindow(calls=5, per=60))
        >>> state.limit, state.remaining
        (5, 4)
    """

    limit: int
    remaining: int
    reset_after: float
