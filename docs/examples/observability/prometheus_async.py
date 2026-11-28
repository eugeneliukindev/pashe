# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.prometheus import PrometheusMetricsHook

metrics = PrometheusMetricsHook()  # one per registry, the global one here: every cache shares it
cache = AsyncCache(AsyncMemoryBackend(), hooks=[metrics])
reports = AsyncCache(AsyncMemoryBackend(), hooks=[metrics])
# --8<-- [end:show]
