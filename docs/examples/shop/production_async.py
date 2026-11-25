from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.compressors import GzipCompressor
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.contrib.redis import AsyncRedisBackend, AsyncRedisTrackingBus
from pashe.options import Fallback

client = Redis.from_url("redis://localhost:6379/0", socket_timeout=0.5)

cache = AsyncCache(
    AsyncNearCacheBackend(
        AsyncMemoryBackend(max_entries=10_000),  # hot entries in the memory of the worker
        AsyncRedisBackend(client),  # shared by every worker of every server
        local_ttl=5,
        bus=AsyncRedisTrackingBus(client, prefix="shop:"),  # a write to Redis drops the copies
    ),
    prefix="shop:",
    codec=MsgspecJsonCodec(),
    fallback=Fallback(AsyncMemoryBackend(max_entries=1_000), ttl=30),
    compressor=GzipCompressor(),  # answers while Redis is down
)
