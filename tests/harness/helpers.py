"""What the tests of both sides share: fakes of a clock, a backend and a source, and calls of either side.

Tests import it as tests.harness.helpers, with the stores of tests.harness.stores and the servers of tests.harness.servers.
"""

from __future__ import annotations

import functools
import importlib.util
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, overload, override

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster
from redis.cluster import RedisCluster

from pashe import AsyncCache, AsyncLocks, AsyncRateLimiter, Cache, Locks, RateLimiter
from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
from pashe._internal.sync.backends.prefixed import PrefixedBackend
from pashe.backends import (
    AsyncBackend,
    AsyncMemoryBackend,
    AsyncNearCacheBackend,
    AsyncSQLiteBackend,
    Backend,
    MemoryBackend,
    NearCacheBackend,
    SQLiteBackend,
)
from pashe.codecs import JsonCodec
from pashe.contrib.redis import AsyncRedisBackend, RedisBackend
from pashe.errors import BackendError
from pashe.hooks import Hook
from pashe.invalidation import InvalidationBus
from pashe.locks import AsyncLock, Lock
from pashe.options import Stale

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from pashe import AsyncCachedBatchFunction, AsyncCachedFunction, CachedBatchFunction, CachedFunction
    from pashe.codecs import Codec
    from pashe.hooks import Failure, Outcome
    from pashe.invalidation import InvalidationHandler


type EitherCache = Cache | AsyncCache
type EitherBackend = Backend | AsyncBackend
type NewCache = Callable[..., EitherCache]  # makes a cache of the side that stands for a process of its own
type EitherLocks = Locks | AsyncLocks
type NewLocks = Callable[..., EitherLocks]  # makes the locks of the side that stand for a process of their own
type EitherLimiter = RateLimiter | AsyncRateLimiter
type NewLimiter = Callable[..., EitherLimiter]  # makes a rate limiter of the side that stands for a process of its own

# A sync call that waits in the loop, as for a busy file, blocks it for seconds; a busy machine of CI
# stalls it for a fifth of a second, the default of pyleak, as it opens a file.
LOOP_BLOCK_SECONDS: Final = 1.0


class Clock:
    """Wall-clock seconds that move only when a test moves them."""

    __slots__ = ("now",)

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


class RecordingHook(Hook):
    """A hook that keeps what a cache tells it in the lists it was given."""

    __slots__ = ("failures", "outcomes")

    def __init__(self, *, outcomes: list[Outcome] | None = None, failures: list[Failure] | None = None) -> None:
        self.outcomes = [] if outcomes is None else outcomes
        self.failures = [] if failures is None else failures

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        self.outcomes.append(outcome)

    @override
    def on_error(self, failure: Failure, /) -> None:
        self.failures.append(failure)


class MemoryBus(InvalidationBus):
    """A bus in memory: every listener of the wire hears every message, the sender too, as with Redis."""

    def __init__(self) -> None:
        self.listeners: list[InvalidationHandler] = []

    @override
    def publish(self, keys: Sequence[str] | None, /) -> None:
        for on_invalidate in self.listeners:
            on_invalidate(None if keys is None else list(keys))

    @override
    def listen(self, on_invalidate: InvalidationHandler, /) -> Callable[[], None]:
        self.listeners.append(on_invalidate)
        return lambda: self.listeners.remove(on_invalidate)


class FailingMemoryBackend(MemoryBackend):
    """A memory backend whose reads and writes fail while down is set, as a backend that is down."""

    __slots__ = ("down",)

    def __init__(self) -> None:
        super().__init__()

        self.down = False

    def _check(self) -> None:
        if self.down:
            msg = "the backend is down"
            raise BackendError(msg)

    @override
    def get(self, key: str, /) -> bytes | None:
        self._check()
        return super().get(key)

    @override
    def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        self._check()
        return super().get_many(keys)

    @override
    def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        self._check()
        super().set(key, value, ttl=ttl)

    @override
    def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        self._check()
        super().set_many(values, ttl=ttl)

    @override
    def incr(
        self,
        key: str,
        by: int,
        /,
        *,
        ttl: float | None = None,
    ) -> int:
        self._check()
        return super().incr(key, by, ttl=ttl)


class AsyncFailingMemoryBackend(AsyncMemoryBackend):
    """The async side of FailingMemoryBackend."""

    __slots__ = ("down",)

    def __init__(self) -> None:
        super().__init__()

        self.down = False

    def _check(self) -> None:
        if self.down:
            msg = "the backend is down"
            raise BackendError(msg)

    @override
    async def get(self, key: str, /) -> bytes | None:
        self._check()
        return await super().get(key)

    @override
    async def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        self._check()
        return await super().get_many(keys)

    @override
    async def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        self._check()
        await super().set(key, value, ttl=ttl)

    @override
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        self._check()
        await super().set_many(values, ttl=ttl)

    @override
    async def incr(
        self,
        key: str,
        by: int,
        /,
        *,
        ttl: float | None = None,
    ) -> int:
        self._check()
        return await super().incr(key, by, ttl=ttl)


@dataclass(frozen=True, slots=True)
class Side:
    """What the tests build of one side of pashe: the classes of Cache, or those of AsyncCache.

    A test of both sides holds what it builds as a union of the two sides, which no type ties to one
    side: a method that joins two of them checks that the one it is given is of its side.
    """

    memory: type[MemoryBackend | AsyncMemoryBackend]
    failing_memory: type[FailingMemoryBackend | AsyncFailingMemoryBackend]
    sqlite: type[SQLiteBackend | AsyncSQLiteBackend]
    is_async: bool

    def new_cache(self, backend: EitherBackend | None = None, **options: Any) -> EitherCache:
        """Return a cache of the side over backend, a new memory backend by default.

        The options go to the cache as they are. A backend of the other side is a TypeError.
        """
        if self.is_async:
            return AsyncCache(AsyncMemoryBackend() if backend is None else _async(backend), **options)
        return Cache(MemoryBackend() if backend is None else _sync(backend), **options)

    def new_locks(self, backend: EitherBackend | None = None, **options: Any) -> EitherLocks:
        """Return the locks of the side over backend, a new memory backend by default; options as new_cache."""
        if self.is_async:
            return AsyncLocks(AsyncMemoryBackend() if backend is None else _async(backend), **options)
        return Locks(MemoryBackend() if backend is None else _sync(backend), **options)

    def new_limiter(self, backend: EitherBackend | None = None, **options: Any) -> EitherLimiter:
        """Return the rate limiter of the side over backend, a new memory backend by default; options as new_cache."""
        if self.is_async:
            return AsyncRateLimiter(AsyncMemoryBackend() if backend is None else _async(backend), **options)
        return RateLimiter(MemoryBackend() if backend is None else _sync(backend), **options)

    def redis(self, url: str) -> RedisBackend | AsyncRedisBackend:
        """Return a Redis backend of the side, with a client of its own to the server at url."""
        if self.is_async:
            return AsyncRedisBackend(AsyncRedis.from_url(url, socket_timeout=1))
        return RedisBackend(Redis.from_url(url, socket_timeout=1))

    def redis_cluster(self, url: str) -> RedisBackend | AsyncRedisBackend:
        """Return a Redis backend of the side, with a client of its own to the cluster of the node at url."""
        if self.is_async:
            return AsyncRedisBackend(AsyncRedisCluster.from_url(url, socket_timeout=1))
        return RedisBackend(RedisCluster.from_url(url, socket_timeout=1))

    def near(self) -> NearCacheBackend | AsyncNearCacheBackend:
        """Return a near cache of the side, with a memory backend as the near store and another as the shared one."""
        if self.is_async:
            return AsyncNearCacheBackend(AsyncMemoryBackend(), AsyncMemoryBackend())
        return NearCacheBackend(MemoryBackend(), MemoryBackend())

    def prefixed(self, backend: EitherBackend, prefix: str) -> PrefixedBackend | AsyncPrefixedBackend:
        """Return backend with every key under prefix. A backend of the other side is a TypeError."""
        if self.is_async:
            return AsyncPrefixedBackend(_async(backend), prefix)
        return PrefixedBackend(_sync(backend), prefix)

    # Any: the result is that of function on the sync side and an awaitable of it on the async one, and
    # the cache that decorates it is a union of both sides, which no type ties to the side of the function
    def function[**P](self, function: Callable[P, object]) -> Callable[P, Any]:
        """Return function as one of the side: itself, or an async def function of its signature that calls it."""
        if not self.is_async:
            return function

        @functools.wraps(function)
        async def awaited(*args: P.args, **kwargs: P.kwargs) -> object:
            return function(*args, **kwargs)

        return awaited


def _sync(backend: EitherBackend) -> Backend:
    # a test joins two things it built of one side: one of the other side is a mistake of the test
    if isinstance(backend, AsyncBackend):
        msg = f"{backend!r} is of the async side, not of the sync one"
        raise TypeError(msg)
    return backend


def _async(backend: EitherBackend) -> AsyncBackend:
    if isinstance(backend, Backend):
        msg = f"{backend!r} is of the sync side, not of the async one"
        raise TypeError(msg)
    return backend


SYNC: Final = Side(memory=MemoryBackend, failing_memory=FailingMemoryBackend, sqlite=SQLiteBackend, is_async=False)
ASYNC: Final = Side(
    memory=AsyncMemoryBackend, failing_memory=AsyncFailingMemoryBackend, sqlite=AsyncSQLiteBackend, is_async=True
)
SIDES: Final = {"sync": SYNC, "async": ASYNC}


@overload
async def call[**P, R](
    function: Callable[P, Awaitable[R]],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R: ...
@overload  # a method of a cache of either side: the union of a def and an async def of one result
async def call[**P, R](
    function: Callable[P, Awaitable[R]] | Callable[P, R],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R: ...
async def call(
    function: Callable[..., object],
    /,
    *args: object,
    **kwargs: object,
) -> object:
    """Call a function of either side and return its result."""
    result = function(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


async def run_block(lock: Lock | AsyncLock) -> None:
    """Enter and leave the block of a lock of either side."""
    if isinstance(lock, AsyncLock):
        async with lock:
            return
    with lock:
        pass


async def close(closing: EitherCache | EitherBackend) -> None:
    """Close a cache of either side, after its background reloads, or a backend."""
    if isinstance(closing, Cache | Backend):
        closing.close()
    else:
        await closing.aclose()


class Source:
    """A function that counts its calls; it fails or answers from its current state."""

    def __init__(self) -> None:
        self.calls = 0
        self.version = 1
        self.error: Exception | None = None

    def __call__(self, user_id: int) -> dict[str, int]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"id": user_id, "version": self.version}


@overload
def cached_function(
    cache: Cache,
    source: Callable[[int], dict[str, int]],
    **options: Any,
) -> CachedFunction[[int], dict[str, int]]: ...
@overload
def cached_function(
    cache: AsyncCache,
    source: Callable[[int], dict[str, int]],
    **options: Any,
) -> AsyncCachedFunction[[int], dict[str, int]]: ...
def cached_function(
    cache: EitherCache,
    source: Callable[[int], dict[str, int]],
    **options: Any,
) -> CachedFunction[[int], dict[str, int]] | AsyncCachedFunction[[int], dict[str, int]]:
    """Return source cached as a def function of user_id by a Cache, or an async def one by an AsyncCache.

    The options go to the decorator as they are.
    """
    if isinstance(cache, Cache):

        def get_user(user_id: int) -> dict[str, int]:
            return source(user_id)

        return cache(**options)(get_user)

    async def aget_user(user_id: int) -> dict[str, int]:
        return source(user_id)

    return cache(**options)(aget_user)


@overload
def batch_function(
    cache: Cache,
    asked: list[list[int]],
    *,
    left_out: frozenset[int] = frozenset(),
    tags: tuple[str, ...] = (),
    stale: Stale = Stale(),
    errors: list[Exception] | None = None,
) -> CachedBatchFunction[int, int]: ...
@overload
def batch_function(
    cache: AsyncCache,
    asked: list[list[int]],
    *,
    left_out: frozenset[int] = frozenset(),
    tags: tuple[str, ...] = (),
    stale: Stale = Stale(),
    errors: list[Exception] | None = None,
) -> AsyncCachedBatchFunction[int, int]: ...
def batch_function(
    cache: EitherCache,
    asked: list[list[int]],
    *,
    left_out: frozenset[int] = frozenset(),
    tags: tuple[str, ...] = (),
    stale: Stale = Stale(),
    errors: list[Exception] | None = None,
) -> CachedBatchFunction[int, int] | AsyncCachedBatchFunction[int, int]:
    """Return a cached batch function of the side of cache.

    It counts what it is asked, leaves left_out out, and raises the first of errors while there is one.
    """
    raised = [] if errors is None else errors

    def answer(ids: list[int]) -> dict[int, int]:
        asked.append(ids)
        if raised:
            raise raised[0]
        return {item_id: item_id * 10 for item_id in ids if item_id not in left_out}

    if isinstance(cache, Cache):

        @cache.batch(ttl=60, key="item:{}", tags=tags, stale=stale)
        def load_items(ids: list[int]) -> dict[int, int]:
            return answer(ids)

        return load_items

    @cache.batch(ttl=60, key="item:{}", tags=tags, stale=stale)
    async def aload_items(ids: list[int]) -> dict[int, int]:
        return answer(ids)

    return aload_items


@overload
def recording_calls[**P, R](
    function: Callable[P, Awaitable[R]], calls: list[tuple[object, ...]]
) -> Callable[P, Awaitable[R]]: ...
@overload
def recording_calls[**P, R](function: Callable[P, R], calls: list[tuple[object, ...]]) -> Callable[P, R]: ...
def recording_calls(function: Callable[..., object], calls: list[tuple[object, ...]]) -> Callable[..., object]:
    """Return function of either side that also notes the positional arguments of every call in calls."""
    if inspect.iscoroutinefunction(function):

        async def acounted(*args: object) -> object:
            calls.append(args)
            return await function(*args)

        return acounted

    def counted(*args: object) -> object:
        calls.append(args)
        return function(*args)

    return counted


def json_codecs() -> list[Codec]:
    """Return the codecs of plain JSON: JsonCodec, and OrjsonCodec where orjson is installed.

    orjson has no build for a Python without the GIL, so the tests run there without it.
    """
    codecs: list[Codec] = [JsonCodec()]
    if importlib.util.find_spec("orjson") is not None:
        from pashe.contrib.orjson import OrjsonCodec  # noqa: PLC0415 - imported only where orjson is installed

        codecs.append(OrjsonCodec())
    return codecs
