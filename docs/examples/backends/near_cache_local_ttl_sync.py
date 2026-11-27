# --8<-- [start:show]
from redis import Redis

from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.redis import RedisBackend

client = Redis.from_url("redis://localhost:6379/0")
backend = NearCacheBackend(
    MemoryBackend(max_entries=1000),
    RedisBackend(client),
    local_ttl=1,  # a copy lives a second: the most a write of another process goes unseen
)
# --8<-- [end:show]
