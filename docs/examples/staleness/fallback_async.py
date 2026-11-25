from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.redis import AsyncRedisBackend
from pashe.options import Fallback

cache = AsyncCache(
    AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0")),
    fallback=Fallback(AsyncMemoryBackend(), ttl=30),
)
