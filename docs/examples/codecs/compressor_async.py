# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.compressors import GzipCompressor

backend = AsyncMemoryBackend()


cache = AsyncCache(backend, compressor=GzipCompressor(level=6))


# --8<-- [end:show]
