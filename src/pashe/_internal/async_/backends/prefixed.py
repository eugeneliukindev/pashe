from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from pashe._internal.async_.backends.backend import AsyncBackend

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


@final
class AsyncPrefixedBackend(AsyncBackend):
    __slots__ = ("_backend", "_prefix")

    def __init__(self, backend: AsyncBackend, prefix: str) -> None:
        self._backend = backend
        self._prefix = prefix

    def full_key(self, key: str) -> str:
        return self._prefix + key

    @override
    async def get(self, key: str, /) -> bytes | None:
        return await self._backend.get(self.full_key(key))

    @override
    async def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        return await self._backend.get_many([self.full_key(key) for key in keys])

    @override
    async def set(self, key: str, value: bytes, /, *, ttl: float | None = None) -> None:
        await self._backend.set(self.full_key(key), value, ttl=ttl)

    @override
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        await self._backend.set_many({self.full_key(key): value for key, value in values.items()}, ttl=ttl)

    @override
    async def set_if_absent(self, key: str, value: bytes, /, *, ttl: float | None = None) -> bool:
        return await self._backend.set_if_absent(self.full_key(key), value, ttl=ttl)

    @override
    async def delete(self, key: str, /) -> bool:
        return await self._backend.delete(self.full_key(key))

    @override
    async def incr(self, key: str, by: int, /, *, ttl: float | None = None) -> int:
        return await self._backend.incr(self.full_key(key), by, ttl=ttl)

    @override
    async def expire(self, key: str, ttl: float, /) -> bool:
        return await self._backend.expire(self.full_key(key), ttl)

    @override
    async def ttl(self, key: str, /) -> float | None:
        return await self._backend.ttl(self.full_key(key))

    @override
    async def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        return await self._backend.delete_if_equals(self.full_key(key), value)

    @override
    async def expire_if_equals(self, key: str, value: bytes, ttl: float, /) -> bool:
        return await self._backend.expire_if_equals(self.full_key(key), value, ttl)

    @override
    async def ping(self) -> None:
        await self._backend.ping()

    @override
    async def aclose(self) -> None:
        await self._backend.aclose()
