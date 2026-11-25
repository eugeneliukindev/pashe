"""Groups of options: of ``@cache(...)``, stale results, stampedes, "not found" and what is stored; of a cache, its fallback.

A group left out takes its defaults; a duration is seconds, or a timedelta. A group checks its
options when it is made and raises InvalidOptionsError for options that cannot work together.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, final

from pashe._internal.checks import (
    DURATION,
    FUNCTION,
    duration_seconds,
    expect_error_classes,
    expect_type,
    parse_seconds,
)
from pashe.errors import InvalidOptionsError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pashe.backends import AsyncBackend, Backend

__all__ = [
    "TTL",
    "Duration",
    "Fallback",
    "IfError",
    "IfSlow",
    "Negative",
    "Stale",
    "Stampede",
    "Store",
    "duration_seconds",
]


_WINDOW: Final = "a window"  # what a window of Stale is, in its errors

type Duration = float | timedelta
"""A span of time: seconds, or a timedelta."""

type TTL = Duration | Callable[[Any], Duration]
"""How long a result is fresh: a Duration, or a function of the result that returns one."""


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Stale:
    """How long after its TTL a stale result still answers, and in which cases; 0 turns a window off.

    Attributes:
        while_revalidate: a stale result answers at once while one caller reloads it in the
            background (RFC 5861).
        if_error: a stale result answers a loader error (RFC 5861): seconds or a timedelta answer
            any Exception; IfError names the errors.
        if_slow: a stale result answers a loader slower than IfSlow.after; the load goes on in
            the background. None turns it off.

    Examples:
        >>> from pashe.options import IfError, IfSlow, Stale
        >>> Stale(while_revalidate=30, if_error=600)
        Stale(while_revalidate=30, if_error=600, if_slow=None)
        >>> Stale(if_error=IfError(600, on=(ConnectionError,)), if_slow=IfSlow(30, after=0.5))
        Stale(while_revalidate=0, if_error=IfError(window=600, on=(<class 'ConnectionError'>,)), if_slow=IfSlow(window=30, after=0.5))
    """

    while_revalidate: Duration = 0
    if_error: Duration | IfError = 0
    if_slow: IfSlow | None = None

    def __post_init__(self) -> None:
        """Check the windows.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: a window is negative.
        """
        parse_seconds("Stale.while_revalidate", self.while_revalidate, _WINDOW)
        expect_type("Stale.if_error", self.if_error, DURATION | IfError)
        if not isinstance(self.if_error, IfError):
            parse_seconds("Stale.if_error", self.if_error, _WINDOW)
        expect_type("Stale.if_slow", self.if_slow, IfSlow | None)


@final
@dataclass(frozen=True, slots=True)
class IfError:
    """How long after its TTL a stale result answers a loader that raised one of on (RFC 5861).

    Attributes:
        window: how long after the TTL, seconds or a timedelta.
        on: the loader errors it answers.

    Examples:
        >>> from pashe.options import IfError
        >>> IfError(600, on=(ConnectionError, TimeoutError))
        IfError(window=600, on=(<class 'ConnectionError'>, <class 'TimeoutError'>))
    """

    window: Duration
    on: tuple[type[Exception], ...] = field(default=(Exception,), kw_only=True)

    def __post_init__(self) -> None:
        """Check the window and the errors.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: the window is negative.
        """
        parse_seconds("IfError.window", self.window, _WINDOW)
        expect_error_classes("IfError.on", self.on)


@final
@dataclass(frozen=True, slots=True)
class IfSlow:
    """How long after its TTL a stale result answers a loader slower than after; the load goes on in the background.

    Attributes:
        window: how long after the TTL, seconds or a timedelta.
        after: how long a call waits for the loader before the stale result answers it.

    Examples:
        >>> from pashe.options import IfSlow
        >>> IfSlow(300, after=0.2)
        IfSlow(window=300, after=0.2)
    """

    window: Duration
    after: Duration = field(kw_only=True)

    def __post_init__(self) -> None:
        """Check the window and the wait.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: the window is negative, or after is not more than 0.
        """
        parse_seconds("IfSlow.window", self.window, _WINDOW)
        parse_seconds("IfSlow.after", self.after, "how long a call waits for the loader", positive=True)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Stampede:
    """How the loads of a key are shared and spread, so the source is not asked by every caller at once.

    Attributes:
        revalidate_before: in the last seconds of its TTL, a fresh result answers at once while
            one caller reloads it in the background, so a key read often never goes stale; 0
            turns it off. It must be shorter than a fixed ttl less its jitter; a ttl from a function shorter
            than it reloads on every call.
        lock_for: when positive, a missing key loads under a lock in the backend: one caller
            loads, the others wait and take its result. It is the longest the lock is held, so
            a holder that dies frees it.
        jitter: spreads TTLs randomly by up to this share, from 0 to less than 1, so entries
            stored together do not expire together: 0.1 means +-10%; the TTL of Negative too.
        max_concurrent_loads: how many loads may run at once in this cache; 0 means no limit.
            A call over it waits for a slot, or raises OverloadedError when a stale result can
            answer instead.
        single_flight: concurrent calls of one key in this cache share one lookup and one
            load. They then get the same object: copy a result before you change it.

    Examples:
        >>> from pashe.options import Stampede
        >>> Stampede(revalidate_before=10, jitter=0.1, lock_for=5)
        Stampede(revalidate_before=10, lock_for=5, jitter=0.1, max_concurrent_loads=0, single_flight=True)
    """

    revalidate_before: Duration = 0
    lock_for: Duration = 0
    jitter: float = 0
    max_concurrent_loads: int = 0
    single_flight: bool = True

    def __post_init__(self) -> None:
        """Check the options.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: jitter is not from 0 to less than 1, or revalidate_before, lock_for or
                max_concurrent_loads is negative.
        """
        parse_seconds(
            "Stampede.revalidate_before",
            self.revalidate_before,
            "0 turns it off, more reloads that long before the TTL",
        )
        expect_type("Stampede.jitter", self.jitter, int | float)
        expect_type("Stampede.single_flight", self.single_flight, bool)
        parse_seconds("Stampede.lock_for", self.lock_for, "0 turns the lock off, more holds it that long")
        expect_type("Stampede.max_concurrent_loads", self.max_concurrent_loads, int)

        if not 0 <= self.jitter < 1:
            msg = f"Stampede.jitter is {self.jitter!r}: a share from 0 to less than 1, such as 0.1 for +-10%"
            raise InvalidOptionsError(msg)

        if self.max_concurrent_loads < 0:
            msg = f"Stampede.max_concurrent_loads is {self.max_concurrent_loads}: 0 means no limit, more is the limit"
            raise InvalidOptionsError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Negative:
    """Negative caching: loader errors that mean "there is no such data", kept as the answer for a while.

    The source is not asked again for what it does not have. The cached function raises
    NotFoundError then, with the loader error as its cause when it loaded; a stale result never
    hides it. By default no error is kept: Negative() turns it off.

    Attributes:
        on: the loader errors that mean "not found", such as ``(UserNotFoundError,)``.
        ttl: how long a "not found" is kept; positive once on names an error.

    Examples:
        >>> from pashe.options import Negative
        >>> Negative(on=(LookupError,), ttl=30)
        Negative(on=(<class 'LookupError'>,), ttl=30)
    """

    on: tuple[type[Exception], ...] = ()
    ttl: Duration = 0

    def __post_init__(self) -> None:
        """Check the options.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: ttl is negative, on names errors without a positive ttl, or ttl is
                set without errors in on.
        """
        expect_error_classes("Negative.on", self.on)
        ttl = parse_seconds("Negative.ttl", self.ttl, "how long a not found is kept")

        if self.on and not ttl:
            msg = f"Negative.on names {len(self.on)} errors and Negative.ttl is 0: set how long a not found is kept"
            raise InvalidOptionsError(msg)

        if ttl and not self.on:
            msg = "Negative.ttl is set and Negative.on is empty: name the loader errors, such as (UserNotFoundError,)"
            raise InvalidOptionsError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Store:
    """Which loaded results are stored; by default every one.

    Attributes:
        when: stores a result only if it returns true, such as ``lambda user: user.active``.
        slower_than: stores only results whose load took at least this many seconds.

    Examples:
        >>> from pashe.options import Store
        >>> Store(slower_than=0.05)
        Store(when=None, slower_than=0.05)
    """

    when: Callable[[Any], bool] | None = None
    slower_than: Duration = 0

    def __post_init__(self) -> None:
        """Check the options.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: slower_than is negative.
        """
        expect_type("Store.when", self.when, FUNCTION | None)
        parse_seconds("Store.slower_than", self.slower_than, "0 stores every result, more stores slow loads only")


@final
@dataclass(frozen=True, slots=True)
class Fallback[B: Backend | AsyncBackend]:
    """Where a cache keeps the results it loads while its backend fails, and for how long.

    The source then gets one load per key and cache instead of one per call. No invalidation
    reaches a result there while the backend is down, so it stays at most ttl, and never past its
    own TTL.

    Attributes:
        backend: where the results are kept, usually a memory backend of the side of the cache.
        ttl: the longest a result stays there: seconds or a timedelta.

    Examples:
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.options import Fallback
        >>> fallback = Fallback(MemoryBackend(max_entries=1000), ttl=60)
    """

    backend: B
    _: KW_ONLY  # noqa: WPS122 - the marker of dataclasses: the fields after it take keywords only
    ttl: Duration = 30

    def __post_init__(self) -> None:
        """Check the options.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive.
        """
        parse_seconds("Fallback.ttl", self.ttl, "the longest a result stays in the fallback", positive=True)
