from __future__ import annotations

import contextlib
import functools
import threading
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Final, final, override

from pashe._internal.async_.backends.backend import AsyncBackend
from pashe._internal.async_.backends.memory import AsyncMemoryBackend
from pashe._internal.checks import parse_seconds, validate_type
from pashe._internal.hooks import Hooks
from pashe.errors import BackendError, ValueTooLargeError
from pashe.hooks import Failure, Hook, NearRead, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from pashe.options import Duration


_STRIPES: Final = 256

type AsyncInvalidationHandler = Callable[[list[str] | None], Awaitable[None]]
"""What a bus calls with the keys others changed; None means every key."""


class AsyncInvalidationBus(ABC):
    """Carries "these keys changed" between near caches; only key names travel.

    Examples:
        A bus of your own implements publish and listen:

        >>> from pashe.invalidation import AsyncInvalidationBus
        >>> class Quiet(AsyncInvalidationBus):
        ...     async def publish(self, keys, /):
        ...         pass
        ...
        ...     def listen(self, on_invalidate, /):
        ...         async def stop():
        ...             pass
        ...
        ...         return stop
    """

    __slots__ = ()

    @abstractmethod
    async def publish(self, keys: Sequence[str] | None, /) -> None:
        """Tell the other near caches that keys changed.

        Args:
            keys: the keys that changed; None means every key.

        Raises:
            BackendError: the message could not be sent.
        """
        raise NotImplementedError

    @abstractmethod
    def listen(self, on_invalidate: AsyncInvalidationHandler, /) -> Callable[[], Awaitable[None]]:
        """Call on_invalidate with the keys others publish, until the returned function is called.

        The sync side listens in a thread of its own, the async side in a task of the running loop.

        Args:
            on_invalidate: receives the keys others changed; None whenever messages may have been lost,
                such as after a reconnect, so every copy goes.

        Returns:
            A function that stops listening.
        """
        raise NotImplementedError


@final
class AsyncNoOpBus(AsyncInvalidationBus):
    """Tells no one: what a near cache has unless it is given a bus.

    The copies of the other near caches then live out their local_ttl after a write.

    Examples:
        >>> from pashe.invalidation import AsyncNoOpBus
        >>> await AsyncNoOpBus().publish(["user:1"])
    """

    __slots__ = ()

    @override
    async def publish(self, keys: Sequence[str] | None, /) -> None:
        """Send nothing.

        Args:
            keys: the keys that changed; no one hears of them.
        """

    @override
    def listen(self, on_invalidate: AsyncInvalidationHandler, /) -> Callable[[], Awaitable[None]]:
        """Hear nothing: on_invalidate is never called.

        Args:
            on_invalidate: what would receive the keys others changed.

        Returns:
            A function that stops listening, which has nothing to stop.
        """
        return _stop_nothing


@final
class AsyncNearCacheBackend(AsyncBackend):
    """Reads through local, then shared: a small cache in memory in front of a shared one.

    Another near cache keeps answering with its copy of a key this one changed for up to local_ttl,
    unless a bus tells it at once. The near cache starts listening to the bus on its first read,
    the async side in the running loop. Closing it stops listening and closes both backends.

    pashe.contrib.redis shows one in front of Redis, with a bus.
    """

    __slots__ = (
        "_bus",
        "_drops",
        "_hooks",
        "_listen_lock",
        "_local",
        "_local_ttl",
        "_publish_failed",
        "_shared",
        "_stop",
    )

    def __init__(
        self,
        local: AsyncMemoryBackend,
        shared: AsyncBackend,
        /,
        *,
        local_ttl: Duration = 5,
        bus: AsyncInvalidationBus = AsyncNoOpBus(),
        hooks: list[Hook] | tuple[Hook, ...] = (),
    ) -> None:
        """Create a near cache.

        Args:
            local: where copies live; its limits bound them.
            shared: where entries live for every cache.
            local_ttl: how long a copy read from shared is kept in local: seconds or a timedelta.
            bus: tells the other near caches which keys this one changed; AsyncNoOpBus, which tells
                no one, by default: the copies of the others then live out local_ttl.
            hooks: what the near cache tells of its reads and of its copies dropped at once, for
                metrics; give it the hooks of the cache over it to see both.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: local_ttl is not positive.
        """
        validate_type("local", local, AsyncMemoryBackend)
        validate_type("shared", shared, AsyncBackend)
        local_ttl = parse_seconds("local_ttl", local_ttl, "how long a copy is kept", positive=True)
        validate_type("bus", bus, AsyncInvalidationBus)

        self._local = local
        self._shared = shared
        self._local_ttl = local_ttl
        self._bus = bus
        self._hooks = Hooks(hooks)

        self._drops = _DropVersions()
        self._listen_lock = threading.Lock()  # one listener, also when threads read at once
        self._stop: Callable[[], Awaitable[None]] | None = None
        self._publish_failed = False  # a drop did not reach the other near caches

    @override
    async def get(self, key: str, /) -> bytes | None:
        self._listen()
        copy = await self._local.get(key)
        self._hooks.on_near_read(
            NearRead(from_local=0, from_shared=1) if copy is None else NearRead(from_local=1, from_shared=0)
        )
        if copy is not None:
            return copy

        version = self._drops.version(key)  # before the read: a drop that comes meanwhile changes it
        value = await self._shared.get(key)
        await self._keep_copy(key, value, version)
        return value

    @override
    async def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        self._listen()
        found = await self._local.get_many(keys)
        indexes = [index for index, value in enumerate(found) if value is None]
        self._hooks.on_near_read(NearRead(from_local=len(keys) - len(indexes), from_shared=len(indexes)))
        if not indexes:
            return found

        missing = [keys[index] for index in indexes]
        versions = [self._drops.version(key) for key in missing]  # before the read, as in get
        values = await self._shared.get_many(missing)
        for index, key, version, value in zip(indexes, missing, versions, values, strict=True):
            found[index] = value
            await self._keep_copy(key, value, version)  # noqa: WPS476 - memory, nothing to win at once
        return found

    @override
    async def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        try:
            await self._shared.set(key, value, ttl=ttl)
        finally:
            await self._drop(key)

    @override
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        try:
            await self._shared.set_many(values, ttl=ttl)
        finally:
            await self._drop(*values)

    @override
    async def set_if_absent(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> bool:
        return await self._write_and_drop(key, functools.partial(self._shared.set_if_absent, key, value, ttl=ttl))

    @override
    async def delete(self, key: str, /) -> bool:
        return await self._write_and_drop(key, functools.partial(self._shared.delete, key))

    @override
    async def incr(
        self,
        key: str,
        by: int,
        /,
        *,
        ttl: float | None = None,
    ) -> int:
        try:
            return await self._shared.incr(key, by, ttl=ttl)
        finally:
            await self._drop(key)

    @override
    async def expire(self, key: str, ttl: float, /) -> bool:
        return await self._write_and_drop(key, functools.partial(self._shared.expire, key, ttl))

    @override
    async def ttl(self, key: str, /) -> float | None:
        return await self._shared.ttl(key)

    @override
    async def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        return await self._write_and_drop(key, functools.partial(self._shared.delete_if_equals, key, value))

    @override
    async def expire_if_equals(
        self,
        key: str,
        value: bytes,
        ttl: float,
        /,
    ) -> bool:
        return await self._shared.expire_if_equals(key, value, ttl)

    @override
    async def ping(self) -> None:
        await self._shared.ping()

    @override
    async def aclose(self) -> None:
        """Stop listening to the bus, and close both backends; the bus shares a client, so it stays open.

        Each is closed even when one before it fails; the error of the last one that failed is raised.
        """
        stop = self._stop
        self._stop = None
        async with contextlib.AsyncExitStack() as closing:  # run in reverse: the bus, local, shared
            closing.push_async_callback(self._shared.aclose)
            closing.push_async_callback(self._local.aclose)
            if stop is not None:
                closing.push_async_callback(stop)

    def _listen(self) -> None:
        if self._stop is not None:
            return  # listening already, as on every read but the first
        with self._listen_lock:
            if self._stop is None:
                self._stop = self._bus.listen(self._on_invalidation)

    async def _keep_copy(
        self,
        key: str,
        value: bytes | None,
        version: int,
    ) -> None:
        """A copy of what the shared backend answered, unless key was dropped since version was read."""
        if value is None or self._drops.version(key) != version:
            return
        try:
            await self._local.set(key, value, ttl=self._local_ttl)
        except ValueTooLargeError:
            return
        if self._drops.version(key) != version:  # a drop of another thread came during the copy and may have missed it
            await self._local.delete(key)

    async def _write_and_drop(self, key: str, write: Callable[[], Awaitable[bool]]) -> bool:
        changed = True  # a write that failed may have changed key
        try:
            changed = await write()
        finally:
            await self._drop(key, publish=changed)
        return changed

    async def _drop(self, *keys: str, publish: bool = True) -> None:
        if not keys:
            return
        self._drops.drop(keys)
        await self._local.delete_many(keys)
        if not publish:
            return
        try:
            if self._publish_failed:  # a drop that did not reach them: they drop every copy, as after a reconnect
                await self._bus.publish(None)
                self._publish_failed = False
            await self._bus.publish(keys)
        except BackendError as error:
            self._publish_failed = True  # until a publish goes through, the others keep their copies up to local_ttl
            self._hooks.on_error(Failure(Operation.PUBLISH, keys[0] if len(keys) == 1 else "", error))

    async def _on_invalidation(self, keys: list[str] | None) -> None:
        self._drops.drop(keys)
        if keys is None:
            await self._local.clear()
            self._hooks.on_near_flush()
        else:
            await self._local.delete_many(keys)


@final
class _DropVersions:
    __slots__ = ("_all", "_lock", "_stripes")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._all = 0
        self._stripes = [0] * _STRIPES  # noqa: WPS435 - ints are immutable: no item is shared

    def version(self, key: str) -> int:
        return self._all + self._stripes[hash(key) % _STRIPES]

    def drop(self, keys: Sequence[str] | None) -> None:
        with self._lock:
            if keys is None:
                self._all += 1
                return
            for key in keys:
                self._stripes[hash(key) % _STRIPES] += 1


async def _stop_nothing() -> None: ...  # what listen of AsyncNoOpBus returns: it listens to nothing
