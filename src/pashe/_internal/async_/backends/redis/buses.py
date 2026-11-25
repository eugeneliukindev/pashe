# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# redis-py is typed in part: what its untyped methods return is unknown to pyright, as to mypy.
# pyright: reportUnusedImport=false
# The sync side keeps the import of redis.asyncio, which it does not use; ruff checks unused imports.
from __future__ import annotations

from typing import TYPE_CHECKING, final, override

# The classes of redis-py by their full names, as a reader of the docs finds them. The sync side keeps
# this import too: redis loads its asyncio package whatever is imported.
import redis.asyncio.cluster  # noqa: WPS301 - it names redis.asyncio and its cluster too

from pashe._internal.async_.backends.near import AsyncInvalidationBus
from pashe._internal.async_.backends.redis.listeners import AsyncPubSubListener, AsyncTrackingListener
from pashe._internal.breakers import Breaker, NoOpBreaker
from pashe._internal.checks import expect_type
from pashe._internal.redis.clients import translated_errors
from pashe._internal.redis.messages import encode_message
from pashe.errors import InvalidOptionsError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from pashe._internal.async_.backends.near import AsyncInvalidationHandler


@final
class AsyncRedisPubSubBus(AsyncInvalidationBus):
    """A near cache bus over Redis pub/sub: every near cache on the channel hears every change.

    It works with Redis, Valkey and a Redis Cluster; the client of a cluster needs pub/sub, which
    redis-py gives the async one from version 8. A message is lost while a near cache is
    disconnected, so after an error it drops all its copies.
    """

    __slots__ = ("_breaker", "_channel", "_client")

    def __init__(
        self,
        client: redis.asyncio.Redis | redis.asyncio.cluster.RedisCluster,
        /,
        *,
        channel: str = "pashe:near-cache",
        breaker: Breaker = NoOpBreaker(),
    ) -> None:
        """Create a bus over client, which it does not close.

        Args:
            client: the client of the backend, or another one of the same Redis.
            channel: the pub/sub channel; the near caches over the same backend use the same one.
            breaker: decides whether a call may reach Redis; give it the breaker of the backend
                over the same Redis, so both skip it together; NoOpBreaker, which skips none, by default.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: client has no pub/sub, as the async RedisCluster of redis-py before 8.

        """
        expect_type("client", client, redis.asyncio.Redis | redis.asyncio.cluster.RedisCluster)
        if not hasattr(client, "pubsub"):  # what every write would raise, at once: AttributeError of publish
            msg = "client has no pub/sub, as a RedisCluster of redis-py before 8: take redis-py 8 or later"
            raise InvalidOptionsError(msg)
        expect_type("channel", channel, str)
        expect_type("breaker", breaker, Breaker)

        self._client = client
        self._channel = channel
        self._breaker = breaker

    @override
    async def publish(self, keys: Sequence[str] | None, /) -> None:
        with self._breaker.guarding(), translated_errors():
            await self._client.publish(self._channel, encode_message(keys))

    @override
    def listen(self, on_invalidate: AsyncInvalidationHandler, /) -> Callable[[], Awaitable[None]]:
        return AsyncPubSubListener(self._client, self._channel, on_invalidate).stop


@final
class AsyncRedisTrackingBus(AsyncInvalidationBus):
    """A near cache bus where Redis itself says which keys changed: CLIENT TRACKING in broadcasting mode.

    Redis tells about every write under prefix by any client, pashe or not, so publish has
    nothing to send. It costs the server no memory, and every near cache hears every write under
    prefix: give the prefix of the cache. It needs Redis or Valkey 6 or later on one node; on a
    Redis Cluster each node tracks only its own keys. The bus listens on a connection of its own
    that speaks RESP2: tracking redirects its messages to that same connection, which subscribes
    to the channel Redis sends them to.
    """

    __slots__ = ("_client", "_prefix")

    def __init__(self, client: redis.asyncio.Redis, /, *, prefix: str = "") -> None:
        """Create a bus over client, which it does not close.

        Args:
            client: the client of the backend, or another one of the same Redis, of one node.
            prefix: the prefix of the cache: only writes of keys under it reach the near caches.

        Raises:
            TypeError: client is not of one node, such as of a Redis Cluster: a node of a cluster
                tracks only its own keys, so take RedisPubSubBus there.
        """
        expect_type("client", client, redis.asyncio.Redis)
        expect_type("prefix", prefix, str)

        self._client = client
        self._prefix = prefix

    @override
    async def publish(self, keys: Sequence[str] | None, /) -> None:
        """Do nothing: Redis tells the other near caches itself.

        Args:
            keys: the keys that changed; Redis saw the writes already.
        """

    @override
    def listen(self, on_invalidate: AsyncInvalidationHandler, /) -> Callable[[], Awaitable[None]]:
        return AsyncTrackingListener(self._client, self._prefix, on_invalidate).stop
