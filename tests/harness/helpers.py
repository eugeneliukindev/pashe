"""What the tests of both sides share: fakes of a clock, a backend and a source, and calls of either side.

Tests import it as tests.harness.helpers, with the stores of tests.harness.stores and the servers of tests.harness.servers.
"""

from __future__ import annotations

import importlib.util
import inspect
from typing import TYPE_CHECKING, Any, override

from pashe import AsyncCache, Cache
from pashe.backends import AsyncMemoryBackend, MemoryBackend
from pashe.codecs import JsonCodec
from pashe.errors import BackendError
from pashe.hooks import Hook
from pashe.invalidation import InvalidationBus

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from pashe.codecs import Codec
    from pashe.hooks import Failure, Outcome
    from pashe.invalidation import InvalidationHandler


type NewCache = Callable[..., Any]  # makes a Cache or an AsyncCache that stands for a process of its own


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
    def set(self, key: str, value: bytes, /, *, ttl: float | None = None) -> None:
        self._check()
        super().set(key, value, ttl=ttl)

    @override
    def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        self._check()
        super().set_many(values, ttl=ttl)

    @override
    def incr(self, key: str, by: int, /, *, ttl: float | None = None) -> int:
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
    async def set(self, key: str, value: bytes, /, *, ttl: float | None = None) -> None:
        self._check()
        await super().set(key, value, ttl=ttl)

    @override
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        self._check()
        await super().set_many(values, ttl=ttl)

    @override
    async def incr(self, key: str, by: int, /, *, ttl: float | None = None) -> int:
        self._check()
        return await super().incr(key, by, ttl=ttl)


def memory(side: str) -> Any:
    """Return an empty memory backend of the side."""
    return MemoryBackend() if side == "sync" else AsyncMemoryBackend()


def failing_memory(side: str) -> Any:
    """Return a memory backend of the side that fails while its down is set."""
    return FailingMemoryBackend() if side == "sync" else AsyncFailingMemoryBackend()


def new_cache(side: str, backend: Any = None, **options: Any) -> Any:
    """Return a Cache or an AsyncCache over backend, a new memory backend by default."""
    backend = backend or memory(side)
    return Cache(backend, **options) if side == "sync" else AsyncCache(backend, **options)


async def call(function: Any, *args: Any, **kwargs: Any) -> Any:
    """Call a function of either side and return its result."""
    result = function(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


async def close(cache: Any) -> None:
    """Wait for the background reloads of a cache of either side."""
    await call(cache.close if isinstance(cache, Cache) else cache.aclose)


class Source:
    """A loader that counts its calls; it fails or answers from its current state."""

    def __init__(self) -> None:
        self.calls = 0
        self.version = 1
        self.error: Exception | None = None

    def __call__(self, user_id: int) -> dict[str, int]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"id": user_id, "version": self.version}


def cached_function(cache: Any, side: str, source: Callable[[int], dict[str, int]], **options: Any) -> Any:
    """Return source cached as a def or an async def function of user_id."""
    if side == "sync":

        def get_user(user_id: int) -> dict[str, int]:
            return source(user_id)

        return cache(**options)(get_user)

    async def aget_user(user_id: int) -> dict[str, int]:
        return source(user_id)

    return cache(**options)(aget_user)


def batch_function(cache: Any, side: str, asked: list[list[int]], *, left_out: frozenset[int] = frozenset()) -> Any:
    """Return a cached batch function of the side: it counts what it is asked, and leaves left_out out."""
    if side == "sync":
        sync_cache: Cache = cache

        @sync_cache.batch(ttl=60, key="item:{}")
        def load_items(ids: list[int]) -> dict[int, int]:
            asked.append(ids)
            return {item_id: item_id * 10 for item_id in ids if item_id not in left_out}

        return load_items

    async_cache: AsyncCache = cache

    @async_cache.batch(ttl=60, key="item:{}")
    async def aload_items(ids: list[int]) -> dict[int, int]:
        asked.append(ids)
        return {item_id: item_id * 10 for item_id in ids if item_id not in left_out}

    return aload_items


def recording_calls(function: Any, calls: list[tuple[object, ...]]) -> Any:
    """Return function of either side that also notes the arguments of every call in calls."""
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
