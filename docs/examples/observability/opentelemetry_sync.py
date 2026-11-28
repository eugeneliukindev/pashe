# --8<-- [start:show]
from redis import Redis

from pashe import Cache
from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook, OtelSpanEventsHook
from pashe.contrib.redis import RedisBackend

metrics = OtelMetricsHook()  # the meter "pashe" of the global provider
shared = RedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1))
near = NearCacheBackend(MemoryBackend(), shared, hooks=[metrics])  # its reads too
cache = Cache(near, hooks=[metrics, OtelSpanEventsHook()])  # and every call as an event of the current span
# --8<-- [end:show]
