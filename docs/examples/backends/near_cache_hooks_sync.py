# --8<-- [start:show]
from redis import Redis

from pashe import Cache
from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook
from pashe.contrib.redis import RedisBackend, RedisPubSubBus

metrics = OtelMetricsHook()
client = Redis.from_url("redis://localhost:6379/0")
backend = NearCacheBackend(
    MemoryBackend(max_entries=1000),
    RedisBackend(client),
    bus=RedisPubSubBus(client, hooks=[metrics]),  # an error while it listens
    hooks=[metrics],  # the keys its copies answered, and when it dropped every copy
)
cache = Cache(backend, hooks=[metrics])
# --8<-- [end:show]
