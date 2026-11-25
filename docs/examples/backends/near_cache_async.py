# --8<-- [start:show]
from redis.asyncio import Redis

from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.redis import AsyncRedisBackend, AsyncRedisTrackingBus

url = "redis://localhost:6379/0"


client = Redis.from_url(url)
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),
    AsyncRedisBackend(client),
    local_ttl=5,
    bus=AsyncRedisTrackingBus(client, prefix="app:"),
)


# --8<-- [end:show]
