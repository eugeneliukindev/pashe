"""Redis and Valkey through redis-py: backends, and buses for near caches; the redis extra.

A backend takes over its client and closes it in ``close``; the client must return bytes, so leave
``decode_responses`` off.

RedisPubSubBus sends the keys pashe changed over pub/sub. RedisTrackingBus lets Redis tell about
every write itself, by anyone, with CLIENT TRACKING; it needs one node, not a cluster. A bus
shares the client of a backend and never closes it.

Examples:
    A cache over Redis; a client connects on its first command:

    >>> from redis import Redis
    >>> from pashe import Cache
    >>> from pashe.contrib.redis import RedisBackend
    >>> cache = Cache(RedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1)))

    The same for async code:

    >>> import redis.asyncio
    >>> from pashe import AsyncCache
    >>> from pashe.contrib.redis import AsyncRedisBackend
    >>> async_cache = AsyncCache(AsyncRedisBackend(redis.asyncio.Redis.from_url("redis://localhost:6379/0")))

    A near cache in front of Redis: the backend and its bus share one client.

    >>> from pashe.backends import MemoryBackend, NearCacheBackend
    >>> from pashe.contrib.redis import RedisTrackingBus
    >>> client = Redis.from_url("redis://localhost:6379/0")
    >>> backend = NearCacheBackend(
    ...     MemoryBackend(max_entries=1000),
    ...     RedisBackend(client),
    ...     local_ttl=5,
    ...     bus=RedisTrackingBus(client, prefix="app:"),
    ... )
"""

from pashe.errors import MissingExtraError

try:
    import redis  # noqa: F401  # pyright: ignore[reportUnusedImport] - first, so a missing extra fails here
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "redis", name=error.name) from error

from pashe._internal.async_.backends.redis.backend import AsyncRedisBackend
from pashe._internal.async_.backends.redis.buses import AsyncRedisPubSubBus, AsyncRedisTrackingBus
from pashe._internal.sync.backends.redis.backend import RedisBackend
from pashe._internal.sync.backends.redis.buses import RedisPubSubBus, RedisTrackingBus

__all__ = [
    "AsyncRedisBackend",
    "AsyncRedisPubSubBus",
    "AsyncRedisTrackingBus",
    "RedisBackend",
    "RedisPubSubBus",
    "RedisTrackingBus",
]
