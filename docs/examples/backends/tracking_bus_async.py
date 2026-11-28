# --8<-- [start:show]
from redis.asyncio import Redis

from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.redis import AsyncRedisBackend, AsyncRedisTrackingBus

shared = AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0"))
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),
    shared,
    bus=AsyncRedisTrackingBus(prefix="app:"),  # the prefix of the cache
)
# --8<-- [end:show]
