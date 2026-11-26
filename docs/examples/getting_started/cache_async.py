from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.redis import AsyncRedisBackend

cache = AsyncCache(AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1)), prefix="app:")
test_cache = AsyncCache(AsyncMemoryBackend())
