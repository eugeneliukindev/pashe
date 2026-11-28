# --8<-- [start:show]
from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.redis import AsyncRedisBackend

client = Redis.from_url("redis://localhost:6379/0")
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),  # the copies of this process, at most 1000
    AsyncRedisBackend(client),  # the entries of every process
)
cache = AsyncCache(backend)
# --8<-- [end:show]
