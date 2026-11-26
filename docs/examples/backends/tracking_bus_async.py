# --8<-- [start:show]
from redis.asyncio import Redis

from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.redis import AsyncRedisBackend, AsyncRedisTrackingBus

client = Redis.from_url("redis://localhost:6379/0", socket_timeout=1)
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),
    AsyncRedisBackend(client),
    bus=AsyncRedisTrackingBus(client, prefix="app:"),  # the prefix of the cache; hears every write, whoever made it
)
# --8<-- [end:show]
