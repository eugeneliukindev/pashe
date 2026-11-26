from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.contrib.redis import AsyncRedisBackend
from pashe.hooks import LoggingHook

cache = AsyncCache(
    AsyncRedisBackend(Redis.from_url("redis://cache:6379/0", socket_timeout=1)),
    prefix="shop:",
    codec=MsgspecJsonCodec(),  # JSON any language reads, without a compressor in front
    hooks=[LoggingHook()],  # a backend that is down is worked around: log it, or no one sees it
)
