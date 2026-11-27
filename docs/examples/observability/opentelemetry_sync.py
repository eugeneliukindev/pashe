# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook, OtelSpanEventsHook

metrics = OtelMetricsHook()  # the meter "pashe" of the global provider
near = NearCacheBackend(MemoryBackend(), MemoryBackend(), hooks=[metrics])  # its reads too
cache = Cache(near, hooks=[metrics, OtelSpanEventsHook()])  # and every call as an event of the current span
# --8<-- [end:show]
