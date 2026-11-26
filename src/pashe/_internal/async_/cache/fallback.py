from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from typing import TYPE_CHECKING, final, override

from pashe._internal.cache.entry import pack
from pashe.errors import BackendError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from pashe._internal.async_.backends.backend import AsyncBackend
    from pashe._internal.cache.entry import Stored
    from pashe.hooks import Hook


class AsyncFallbackStore(ABC):
    # Where a cache keeps what it loads while its backend fails: one per cache, made with it.
    __slots__ = ()

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        # the entry kept under key; None if there is none, or if the fallback failed
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, stored: Stored | None) -> None:
        # keep stored under key, untagged: no invalidation reaches it while the backend is down;
        # None, what the policy did not store, keeps nothing
        raise NotImplementedError

    @abstractmethod
    async def aclose(self) -> None:
        raise NotImplementedError


@final
class AsyncBackendFallbackStore(AsyncFallbackStore):
    __slots__ = ("_backend", "_hooks", "_ttl")

    def __init__(
        self,
        backend: AsyncBackend,
        *,
        ttl: float,
        hooks: Hook,
    ) -> None:
        self._backend = backend
        self._ttl = ttl  # the longest an entry stays, in seconds
        self._hooks = hooks

    @override
    async def get(self, key: str) -> bytes | None:
        try:
            return await self._backend.get(key)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.FALLBACK_GET, key, error))
            return None

    @override
    async def set(self, key: str, stored: Stored | None) -> None:
        if stored is None:
            return
        kept_for = min(stored.fresh_seconds, self._ttl) if stored.fresh_seconds > 0 else self._ttl
        try:
            await self._backend.set(key, pack(replace(stored.entry, tag_generations=())), ttl=kept_for)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.FALLBACK_SET, key, error))

    @override
    async def aclose(self) -> None:
        await self._backend.aclose()


@final
class AsyncNoOpFallbackStore(AsyncFallbackStore):
    # what a cache without a fallback has: it keeps nothing, and finds nothing
    __slots__ = ()

    @override
    async def get(self, key: str) -> bytes | None:
        """Find nothing: the cache has no fallback."""

    @override
    async def set(self, key: str, stored: Stored | None) -> None:
        """Keep nothing: the cache has no fallback."""

    @override
    async def aclose(self) -> None:
        """Close nothing: the cache has no fallback."""
