# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# redis-py is typed in part: what its untyped methods return is unknown to pyright, as to mypy.
# pyright: reportUnusedImport=false
# The sync side keeps the import of redis.asyncio, which it does not use; ruff checks unused imports.
# mypy: disable-error-code="unused-awaitable"
# A command queued on a pipeline returns the pipeline; execute runs them all.
from __future__ import annotations

from typing import TYPE_CHECKING, final, override

# The classes of redis-py by their full names, as a reader of the docs finds them. The sync side keeps
# this import too: redis loads its asyncio package whatever is imported.
import redis.asyncio.cluster  # noqa: WPS301 - it names redis.asyncio and its cluster too

from pashe._internal.async_.backends.backend import AsyncBackend
from pashe._internal.breakers import Breaker, NoOpBreaker
from pashe._internal.checks import expect_int64, expect_type
from pashe._internal.redis.clients import (  # noqa: WPS235 - what both sides share about Redis is one module, read whole
    DELETE_IF_EQUALS,
    EXPIRE_IF_EQUALS,
    INCR_WITH_TTL,
    check_client,
    milliseconds,
    px,
    seconds_left,
    translated_errors,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


@final
class AsyncRedisBackend(AsyncBackend):
    """A backend over Redis or Valkey through a redis-py client of its side, of one node or of a cluster.

    ``redis.Redis`` or ``redis.cluster.RedisCluster`` for sync code, their ``redis.asyncio``
    twins for async. pashe.contrib.redis shows how to make one.

    On a cluster every command but those of many keys reaches the one node of its key; the
    commands of many keys are split by node, as pashe needs no atomicity across keys.
    """

    __slots__ = ("_breaker", "_client", "_delete_if_equals", "_expire_if_equals", "_get_many", "_incr_with_ttl")

    def __init__(
        self, client: redis.asyncio.Redis | redis.asyncio.cluster.RedisCluster, /, *, breaker: Breaker = NoOpBreaker()
    ) -> None:
        """Create a backend over client; the backend closes it.

        Args:
            client: a redis-py client of the side of the backend, of one node or of a cluster,
                without decode_responses, as a backend stores bytes, and with socket_timeout, so a
                Redis that hangs fails a call instead of holding it.
            breaker: decides whether a call may reach Redis, such as a CircuitBreaker that skips it for a
                while after it failed several times in a row; NoOpBreaker, which skips none, by default.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: client has decode_responses on, or no socket_timeout.
        """
        expect_type("client", client, redis.asyncio.Redis | redis.asyncio.cluster.RedisCluster)
        check_client(client)
        expect_type("breaker", breaker, Breaker)

        self._client = client
        self._breaker = breaker

        # a cluster refuses MGET across slots; mget_nonatomic sends one MGET per node instead
        self._get_many = (
            client.mget_nonatomic if isinstance(client, redis.asyncio.cluster.RedisCluster) else client.mget
        )

        self._delete_if_equals = client.register_script(DELETE_IF_EQUALS)
        self._expire_if_equals = client.register_script(EXPIRE_IF_EQUALS)
        self._incr_with_ttl = client.register_script(INCR_WITH_TTL)

    @override
    async def get(self, key: str, /) -> bytes | None:
        with self._breaker.guarding(), translated_errors():
            return await self._client.get(key)  # type: ignore[return-value]  # bytes: decode_responses is off

    @override
    async def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        if not keys:  # no call to Redis: the breaker has no say
            return []
        with self._breaker.guarding(), translated_errors():
            return await self._get_many(keys)  # type: ignore[return-value]  # bytes, as above

    @override
    async def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        with self._breaker.guarding(), translated_errors():
            await self._client.set(key, value, px=px(ttl))

    @override
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        if not values:  # as in get_many
            return
        with self._breaker.guarding(), translated_errors():
            pipeline = self._client.pipeline(transaction=False)  # on a cluster, one per node
            for key, value in values.items():
                pipeline.set(key, value, px=px(ttl))
            await pipeline.execute()

    @override
    async def set_if_absent(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> bool:
        with self._breaker.guarding(), translated_errors():
            return bool(await self._client.set(key, value, px=px(ttl), nx=True))

    @override
    async def delete(self, key: str, /) -> bool:
        with self._breaker.guarding(), translated_errors():
            return bool(await self._client.delete(key))

    @override
    async def incr(
        self,
        key: str,
        by: int,
        /,
        *,
        ttl: float | None = None,
    ) -> int:
        expect_int64("redis.by", by)
        with self._breaker.guarding(), translated_errors():
            if ttl is None:
                return await self._client.incrby(key, by)
            return await self._incr_with_ttl(keys=[key], args=[by, milliseconds(ttl)])  # type: ignore[no-any-return]  # INCRBY: an int

    @override
    async def expire(self, key: str, ttl: float, /) -> bool:
        with self._breaker.guarding(), translated_errors():
            return await self._client.pexpire(key, milliseconds(ttl))

    @override
    async def ttl(self, key: str, /) -> float | None:
        with self._breaker.guarding(), translated_errors():
            return seconds_left(await self._client.pttl(key))

    @override
    async def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        with self._breaker.guarding(), translated_errors():
            return bool(await self._delete_if_equals(keys=[key], args=[value]))

    @override
    async def expire_if_equals(
        self,
        key: str,
        value: bytes,
        ttl: float,
        /,
    ) -> bool:
        with self._breaker.guarding(), translated_errors():
            return bool(await self._expire_if_equals(keys=[key], args=[value, milliseconds(ttl)]))

    @override
    async def ping(self) -> None:
        with self._breaker.guarding(), translated_errors():
            await self._client.ping()

    @override
    async def aclose(self) -> None:
        await self._client.aclose()
