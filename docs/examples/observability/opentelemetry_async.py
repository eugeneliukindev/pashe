# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend, AsyncNearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook, OtelSpanEventsHook

metrics = OtelMetricsHook()  # the meter "pashe" of the global provider
near = AsyncNearCacheBackend(AsyncMemoryBackend(), AsyncMemoryBackend(), hooks=[metrics])  # its reads too
cache = AsyncCache(near, hooks=[metrics, OtelSpanEventsHook()])  # and every call as an event of the current span
# --8<-- [end:show]
