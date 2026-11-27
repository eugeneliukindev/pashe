from __future__ import annotations

import contextlib
import contextvars
import time
from typing import TYPE_CHECKING, Final, NamedTuple, Self, final

from pashe.hooks import CacheStatus, Hook, Outcome

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from types import TracebackType

    from pashe._internal.cache.entry import Stored


_NO_CACHE: Final = contextvars.ContextVar("pashe_no_cache", default=False)


@final
class Call(NamedTuple):
    # one call of a cached function, as it goes from the read to the store
    key: str
    tags: tuple[str, ...]
    changes_at_start: int  # the sets and deletes by hand of its function cache when it started
    stopwatch: Stopwatch

    def restarted(self) -> Self:
        """The same call for a load apart from it, which times itself."""
        return self._replace(stopwatch=Stopwatch())


@final
class Answer(NamedTuple):
    result: object  # decoded as the return type
    status: CacheStatus
    load_seconds: float = 0
    stale_at: float | None = None  # when the result stops being fresh; None if it was not kept

    @classmethod
    def of(
        cls,
        stored: Stored,
        status: CacheStatus,
        load_seconds: float = 0,
    ) -> Self:
        return cls(stored.result, status, load_seconds, stored.entry.stale_at)


@final
class Stopwatch:
    # The seconds the function ran for one call, a failed load included, as its Outcome reports:
    # each with block around a load adds its time.
    __slots__ = ("_start", "seconds")

    def __init__(self) -> None:
        self.seconds: float = 0
        self._start: float = 0

    def __enter__(self) -> None:
        self._start = time.perf_counter()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.seconds += time.perf_counter() - self._start


@final
class CallReporter:
    # tells the hooks how every call of one cached function was answered
    __slots__ = ("_clock", "_function", "_hooks", "_prefix")

    def __init__(
        self,
        function: str,
        prefix: str,
        *,
        hooks: Hook,
        clock: Callable[[], float],
    ) -> None:
        self._function = function  # the qualified name of the function
        self._prefix = prefix  # of the cache: the hooks are told the keys as the backend keeps them
        self._hooks = hooks
        self._clock = clock

    def report(
        self,
        key: str,
        status: CacheStatus,
        *,
        load_seconds: float = 0,
        stale_at: float | None = None,
    ) -> None:
        left = None if stale_at is None else stale_at - self._clock()
        self._hooks.on_call(Outcome(self._function, self._prefix + key, status, load_seconds, left))


@contextlib.contextmanager
def no_cache() -> Generator[None]:
    """Answer no call from a stored result in the block: every cached call loads, and stores what it loaded.

    It holds for every cache, in the thread or the task of the block, as ``Cache-Control:
    no-cache`` of a request does. The calls after the block get the result stored in it; get
    of a cached function returns None in it.

    Examples:
        >>> import pashe
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> cache, loads = Cache(MemoryBackend()), []
        >>> @cache(ttl=60)
        ... def get_user(user_id: int) -> int:
        ...     loads.append(user_id)
        ...     return user_id
        >>> get_user(1), get_user(1)
        (1, 1)
        >>> with pashe.no_cache():
        ...     get_user(1)
        1
        >>> len(loads)
        2
    """
    token = _NO_CACHE.set(True)
    try:
        yield
    finally:
        _NO_CACHE.reset(token)


def in_no_cache() -> bool:
    """Whether the context runs inside no_cache."""
    return _NO_CACHE.get()
