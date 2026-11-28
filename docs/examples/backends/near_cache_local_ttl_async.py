# --8<-- [start:show]
from redis.asyncio import Redis

from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.redis import AsyncRedisBackend

client = Redis.from_url("redis://localhost:6379/0")
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),
    AsyncRedisBackend(client),
    local_ttl=1,  # a copy lives a second: the most a write of another process goes unseen
)
# --8<-- [end:show]
