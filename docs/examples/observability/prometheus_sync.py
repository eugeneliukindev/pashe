# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.prometheus import PrometheusMetricsHook

metrics = PrometheusMetricsHook()  # one per registry, the global one here: every cache shares it
cache = Cache(MemoryBackend(), hooks=[metrics])
reports = Cache(MemoryBackend(), hooks=[metrics])
# --8<-- [end:show]
