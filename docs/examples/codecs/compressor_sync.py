# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.compressors import GzipCompressor

backend = MemoryBackend()


cache = Cache(backend, compressor=GzipCompressor(level=6))


# --8<-- [end:show]
