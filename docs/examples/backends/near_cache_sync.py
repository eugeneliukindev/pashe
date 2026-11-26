# --8<-- [start:show]
from redis import Redis

from pashe.backends import MemoryBackend, NearCacheBackend
from pashe.contrib.redis import RedisBackend, RedisTrackingBus

url = "redis://localhost:6379/0"


client = Redis.from_url(url, socket_timeout=1)
backend = NearCacheBackend(
    MemoryBackend(max_entries=1000),
    RedisBackend(client),
    local_ttl=5,
    bus=RedisTrackingBus(client, prefix="app:"),
)


# --8<-- [end:show]
