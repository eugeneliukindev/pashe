from __future__ import annotations

import contextlib
import contextvars
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from pashe.hooks import CacheStatus, Hook, Outcome

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pashe._internal.cache.entry import Generations


_NO_CACHE: Final = contextvars.ContextVar("pashe_no_cache", default=False)


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
    # whether the context runs inside no_cache
    return _NO_CACHE.get()


@final
@dataclass(slots=True)
class CallState:
    # one call of a cached function, as it goes from the read to the store
    key: str
    tags: tuple[str, ...] = ()
    tag_generations: Generations = ()  # read before the load: a tag invalidated during it makes the entry a miss
    load_seconds: float = 0
    has_stale_answer: bool = False  # a stale result can answer if the load fails or waits for a slot
    changes_at_start: int = 0  # the sets and deletes by hand of its function cache when it started


@final
@dataclass(frozen=True, slots=True)
class Answer:
    value: object  # decoded as the return type
    status: CacheStatus
    load_seconds: float = 0
    stale_at: float | None = None  # when the result stops being fresh; None if it was not stored


@final
class CallReporter:
    # tells the hooks how every call of one cached function was answered
    __slots__ = ("_clock", "_full_key", "_function", "_hooks")

    def __init__(
        self,
        function: str,
        full_key: Callable[[str], str],
        *,
        hooks: Hook,
        clock: Callable[[], float],
    ) -> None:
        self._function = function  # the qualified name of the function
        self._full_key = full_key  # the key with the prefix of the cache
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
        self._hooks.on_call(Outcome(self._function, self._full_key(key), status, load_seconds, left))


@contextlib.contextmanager
def timed(state: CallState) -> Generator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        state.load_seconds += time.perf_counter() - start
