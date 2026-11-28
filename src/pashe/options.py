"""Groups of options: of ``@cache(...)``, stale results, stampedes, "not found" and what is stored; of a cache, its fallback.

A group left out takes its defaults; a duration is seconds, or a timedelta. A group checks its
options when it is made and raises InvalidOptionsError for options that cannot work together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, final

from pashe._internal.checks import (
    FUNCTION,
    duration_seconds,
    parse_seconds,
    validate_error_classes,
    validate_type,
)
from pashe.errors import InvalidOptionsError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pashe.backends import AsyncBackend, Backend

__all__ = [
    "TTL",
    "Duration",
    "Fallback",
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
@dataclass(frozen=True, slots=True, init=False)
class Stale:
    """How long after its TTL a stale result still answers, and in which cases; 0 turns a window off.

    Attributes:
        while_revalidate: seconds a stale result answers at once while one caller reloads it in
            the background (RFC 5861).
        if_error: seconds a stale result answers an error of the function of if_error_on (RFC 5861).
        if_error_on: the errors of the function if_error answers.
        if_slow: seconds a stale result answers a function slower than slow_after, while the load
            goes on in the background.
        slow_after: how long a call waits for the function before the stale result answers it, in
            seconds; more than 0 once if_slow is.

    Examples:
        >>> from pashe.options import Stale
        >>> Stale(while_revalidate=30, if_error=600, if_error_on=(ConnectionError,))
        Stale(while_revalidate=30.0, if_error=600.0, if_error_on=(<class 'ConnectionError'>,), if_slow=0.0, slow_after=0.0)
        >>> Stale(if_slow=30, slow_after=0.5).slow_after
        0.5
    """

    while_revalidate: float
    if_error: float
    if_error_on: tuple[type[Exception], ...]
    if_slow: float
    slow_after: float

    def __init__(
        self,
        *,
        while_revalidate: Duration = 0,
        if_error: Duration = 0,
        if_error_on: tuple[type[Exception], ...] = (Exception,),
        if_slow: Duration = 0,
        slow_after: Duration = 0,
    ) -> None:
        """Check the windows and keep them in seconds.

        Args:
            while_revalidate: seconds or a timedelta.
            if_error: seconds or a timedelta.
            if_error_on: the errors of the function it answers; every Exception by default.
            if_slow: seconds or a timedelta.
            slow_after: seconds or a timedelta.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: a window is negative, if_error_on names errors while if_error is 0,
                or one of if_slow and slow_after is set without the other.
        """
        validate_error_classes("Stale.if_error_on", if_error_on)
        if_error = parse_seconds("Stale.if_error", if_error, _WINDOW)
        if_slow = parse_seconds("Stale.if_slow", if_slow, _WINDOW)
        slow_after = parse_seconds("Stale.slow_after", slow_after, "how long a call waits for the function")
        if if_error_on != (Exception,) and not if_error:
            msg = "Stale.if_error_on names errors and Stale.if_error is 0: set how long the stale result answers them"
            raise InvalidOptionsError(msg)
        if bool(if_slow) != bool(slow_after):
            msg = (
                f"Stale.if_slow is {if_slow:g} and Stale.slow_after is {slow_after:g}: set both, how long the stale"
                " result answers a slow function and how long a call waits for it"
            )
            raise InvalidOptionsError(msg)

        object.__setattr__(self, "while_revalidate", parse_seconds("Stale.while_revalidate", while_revalidate, _WINDOW))
        object.__setattr__(self, "if_error", if_error)
        object.__setattr__(self, "if_error_on", if_error_on)
        object.__setattr__(self, "if_slow", if_slow)
        object.__setattr__(self, "slow_after", slow_after)


@final
@dataclass(frozen=True, slots=True, init=False)
class Stampede:
    """How the loads of a key are shared and spread, so the source is not asked by every caller at once.

    Attributes:
        revalidate_before: in the last seconds of its TTL, a fresh result answers at once while
            one caller reloads it in the background, so a key read often never goes stale; 0
            turns it off. It must be shorter than a fixed ttl less its jitter; a ttl from a function shorter
            than it reloads on every call.
        lock_for: when positive, a missing key loads under a lock in the backend: one caller
            loads, the others wait and take its result. It is the longest the lock is held, in
            seconds, so a holder that dies frees it.
        jitter: spreads TTLs randomly by up to this share, from 0 to less than 1, so entries
            stored together do not expire together: 0.1 means +-10%; the TTL of Negative too.
        max_loads: how many loads of the function may run at once in this process; 0 means no
            limit. A call over it waits for a slot; when a stale result can answer it, that result
            answers at once instead, and the hooks hear an OverloadedError.
        share_loads: concurrent calls of one key in this process share one lookup and one
            load. They then get the same object: copy a result before you change it.

    Examples:
        >>> from pashe.options import Stampede
        >>> Stampede(revalidate_before=10, jitter=0.1, lock_for=5)
        Stampede(revalidate_before=10.0, lock_for=5.0, jitter=0.1, max_loads=0, share_loads=True)
    """

    revalidate_before: float
    lock_for: float
    jitter: float
    max_loads: int
    share_loads: bool

    def __init__(
        self,
        *,
        revalidate_before: Duration = 0,
        lock_for: Duration = 0,
        jitter: float = 0,
        max_loads: int = 0,
        share_loads: bool = True,
    ) -> None:
        """Check the options and keep the durations in seconds.

        Args:
            revalidate_before: seconds or a timedelta.
            lock_for: seconds or a timedelta.
            jitter: a share from 0 to less than 1.
            max_loads: 0 or more.
            share_loads: whether concurrent calls of a key share one load.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: jitter is not from 0 to less than 1, or revalidate_before, lock_for or
                max_loads is negative.
        """
        validate_type("Stampede.jitter", jitter, int | float)
        validate_type("Stampede.max_loads", max_loads, int)
        validate_type("Stampede.share_loads", share_loads, bool)
        if not 0 <= jitter < 1:
            msg = f"Stampede.jitter is {jitter!r}: a share from 0 to less than 1, such as 0.1 for +-10%"
            raise InvalidOptionsError(msg)
        if max_loads < 0:
            msg = f"Stampede.max_loads is {max_loads}: 0 means no limit, more is the limit"
            raise InvalidOptionsError(msg)

        revalidate_before = parse_seconds(
            "Stampede.revalidate_before", revalidate_before, "0 turns it off, more reloads that long before the TTL"
        )
        lock_for = parse_seconds("Stampede.lock_for", lock_for, "0 turns the lock off, more holds it that long")
        object.__setattr__(self, "revalidate_before", revalidate_before)
        object.__setattr__(self, "lock_for", lock_for)
        object.__setattr__(self, "jitter", float(jitter))
        object.__setattr__(self, "max_loads", max_loads)
        object.__setattr__(self, "share_loads", share_loads)


@final
@dataclass(frozen=True, slots=True, init=False)
class Negative:
    """Negative caching: errors of the function that mean "there is no such data", kept as the answer for a while.

    The source is not asked again for what it does not have. The cached function raises
    NotFoundError then, with the error of the function as its cause when it loaded; a stale result never
    hides it. By default no error is kept: Negative() turns it off.

    Attributes:
        on: the errors of the function that mean "not found", such as ``(UserNotFoundError,)``.
        ttl: how long a "not found" is kept, in seconds; positive once on names an error.

    Examples:
        >>> from pashe.options import Negative
        >>> Negative(on=(LookupError,), ttl=30)
        Negative(on=(<class 'LookupError'>,), ttl=30.0)
    """

    on: tuple[type[Exception], ...]
    ttl: float

    def __init__(self, *, on: tuple[type[Exception], ...] = (), ttl: Duration = 0) -> None:
        """Check the options and keep ttl in seconds.

        Args:
            on: the errors of the function that mean "not found".
            ttl: seconds or a timedelta.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: ttl is negative, on names errors without a positive ttl, or ttl is
                set without errors in on.
        """
        validate_error_classes("Negative.on", on)
        seconds = parse_seconds("Negative.ttl", ttl, "how long a not found is kept")
        if on and not seconds:
            msg = f"Negative.on names {len(on)} errors and Negative.ttl is 0: set how long a not found is kept"
            raise InvalidOptionsError(msg)
        if seconds and not on:
            msg = "Negative.ttl is set and Negative.on is empty: name the errors of the function, such as (UserNotFoundError,)"
            raise InvalidOptionsError(msg)

        object.__setattr__(self, "on", on)
        object.__setattr__(self, "ttl", seconds)


@final
@dataclass(frozen=True, slots=True, init=False)
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

    when: Callable[[Any], bool] | None
    slower_than: float

    def __init__(self, *, when: Callable[[Any], bool] | None = None, slower_than: Duration = 0) -> None:
        """Check the options and keep slower_than in seconds.

        Args:
            when: a function of the result, or None to store every one.
            slower_than: seconds or a timedelta.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: slower_than is negative.
        """
        validate_type("Store.when", when, FUNCTION | None)

        object.__setattr__(self, "when", when)
        object.__setattr__(
            self,
            "slower_than",
            parse_seconds("Store.slower_than", slower_than, "0 stores every result, more stores slow loads only"),
        )


@final
@dataclass(frozen=True, slots=True, init=False)
class Fallback[B: Backend | AsyncBackend]:
    """Where a cache keeps the results it loads while its backend fails, and for how long.

    The source then gets one load per key and cache instead of one per call. No invalidation
    reaches a result there while the backend is down, so it stays at most ttl, and never past its
    own TTL.

    Attributes:
        backend: where the results are kept, usually a memory backend of the side of the cache.
        ttl: the longest a result stays there, in seconds.

    Examples:
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.options import Fallback
        >>> fallback = Fallback(MemoryBackend(max_entries=1000), ttl=60)
    """

    backend: B
    ttl: float

    def __init__(self, backend: B, *, ttl: Duration = 30) -> None:
        """Check the options and keep ttl in seconds.

        Args:
            backend: where the results are kept.
            ttl: seconds or a timedelta, more than 0.

        Raises:
            TypeError: an option is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive.
        """
        object.__setattr__(self, "backend", backend)
        object.__setattr__(
            self, "ttl", parse_seconds("Fallback.ttl", ttl, "the longest a result stays in the fallback", positive=True)
        )
