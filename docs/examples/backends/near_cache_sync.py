# --8<-- [start:show]
from redis import Redis

from pashe import Cache
from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.redis import RedisBackend

client = Redis.from_url("redis://localhost:6379/0")
backend = NearCacheBackend(
    MemoryBackend(max_entries=1000),  # the copies of this process, at most 1000
    RedisBackend(client),  # the entries of every process
)
cache = Cache(backend)
# --8<-- [end:show]
