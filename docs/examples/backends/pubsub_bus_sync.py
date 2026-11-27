# --8<-- [start:show]
from redis import Redis

from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.redis import RedisBackend, RedisPubSubBus

client = Redis.from_url("redis://localhost:6379/0")
backend = NearCacheBackend(
    MemoryBackend(max_entries=1000),
    RedisBackend(client),
    bus=RedisPubSubBus(client, channel="pashe:near-cache"),  # the default channel
)
# --8<-- [end:show]
