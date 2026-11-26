# --8<-- [start:show]
from redis.asyncio import Redis

from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.redis import AsyncRedisBackend, AsyncRedisPubSubBus

client = Redis.from_url("redis://localhost:6379/0")
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),
    AsyncRedisBackend(client),
    bus=AsyncRedisPubSubBus(
        client, channel="pashe:near-cache"
    ),  # the default channel; hears the writes made through pashe
)
# --8<-- [end:show]
