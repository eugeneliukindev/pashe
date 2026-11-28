from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.contrib.msgspec import MsgspecMsgpackCodec
from pashe.contrib.redis import AsyncRedisBackend
from pashe.contrib.zstd import ZstdCompressor
from pashe.hooks import LoggingHook

cache = AsyncCache(
    AsyncRedisBackend(Redis.from_url("redis://cache:6379/0", socket_timeout=1)),
    prefix="shop:",
    codec=MsgspecMsgpackCodec(),  # the smallest of the codecs that rebuild your types
    hooks=[LoggingHook()],  # a backend that is down is worked around: log it, or no one sees it
    compressor=ZstdCompressor(),  # when values are kilobytes; see below
)
