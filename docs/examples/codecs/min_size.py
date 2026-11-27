from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.compressors import GzipCompressor

cache = Cache(MemoryBackend(), compressor=GzipCompressor(min_size=4096))  # values of 4 KiB or more
