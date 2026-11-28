# --8<-- [start:show]
from redis import Redis

from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.redis import RedisBackend, RedisTrackingBus

shared = RedisBackend(Redis.from_url("redis://localhost:6379/0"))
backend = NearCacheBackend(
    MemoryBackend(max_entries=1000),
    shared,
    bus=RedisTrackingBus(prefix="app:"),  # the prefix of the cache
)
# --8<-- [end:show]
