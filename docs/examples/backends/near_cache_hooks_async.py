# --8<-- [start:show]
from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook
from pashe.contrib.redis import AsyncRedisBackend, AsyncRedisPubSubBus

metrics = OtelMetricsHook()
client = Redis.from_url("redis://localhost:6379/0")
backend = AsyncNearCacheBackend(
    AsyncMemoryBackend(max_entries=1000),
    AsyncRedisBackend(client),
    bus=AsyncRedisPubSubBus(client, hooks=[metrics]),  # an error while it listens
    hooks=[metrics],  # the keys its copies answered, and when it dropped every copy
)
cache = AsyncCache(backend, hooks=[metrics])
# --8<-- [end:show]
