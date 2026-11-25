from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.contrib.pydantic import PydanticCodec
from pashe.contrib.redis import AsyncRedisBackend
from pashe.hooks import LoggingHook

cache = AsyncCache(
    AsyncRedisBackend(Redis.from_url("redis://cache:6379/0")),
    prefix="shop:",
    codec=PydanticCodec(),  # rebuilds the models your functions return
    hooks=[LoggingHook()],  # a backend that is down is worked around: log it, or no one sees it
)
