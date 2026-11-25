# --8<-- [start:show]
from pashe import AsyncCache, Cache
from pashe.backends import AsyncMemoryBackend, MemoryBackend
from pashe.contrib.prometheus import PrometheusMetricsHook

metrics = PrometheusMetricsHook()  # one per registry, the global one here: every cache shares it
cache = AsyncCache(AsyncMemoryBackend(), hooks=[metrics])
reports = Cache(MemoryBackend(), hooks=[metrics])
# --8<-- [end:show]
