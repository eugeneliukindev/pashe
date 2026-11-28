# --8<-- [start:show]
from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook, OtelSpanEventsHook
from pashe.contrib.redis import AsyncRedisBackend

metrics = OtelMetricsHook()  # the meter "pashe" of the global provider
shared = AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1))
near = AsyncNearCacheBackend(AsyncMemoryBackend(), shared, hooks=[metrics])  # its reads too
cache = AsyncCache(near, hooks=[metrics, OtelSpanEventsHook()])  # and every call as an event of the current span
# --8<-- [end:show]
