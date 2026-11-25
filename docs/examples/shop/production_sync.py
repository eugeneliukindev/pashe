from redis import Redis

from pashe import Cache
from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.compressors import GzipCompressor
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.contrib.redis import RedisBackend, RedisTrackingBus
from pashe.options import Fallback

client = Redis.from_url("redis://localhost:6379/0", socket_timeout=0.5)

cache = Cache(
    NearCacheBackend(
        MemoryBackend(max_entries=10_000),  # hot entries in the memory of the worker
        RedisBackend(client),  # shared by every worker of every server
        local_ttl=5,
        bus=RedisTrackingBus(client, prefix="shop:"),  # a write to Redis drops the copies
    ),
    prefix="shop:",
    codec=MsgspecJsonCodec(),
    fallback=Fallback(MemoryBackend(max_entries=1_000), ttl=30),
    compressor=GzipCompressor(),  # answers while Redis is down
)
