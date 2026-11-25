# --8<-- [start:show]
from redis import Redis

from pashe import Cache
from pashe.backends import CircuitBreaker, MemoryBackend
from pashe.contrib.redis import RedisBackend
from pashe.options import Fallback

client = Redis.from_url(
    "redis://localhost:6379/0",
    socket_connect_timeout=0.1,  # a Redis that is down costs 0.1 s, not the default wait
    socket_timeout=0.2,
)
breaker = CircuitBreaker(failure_threshold=5, open_for=10)  # 5 failures in a row: skip Redis for 10 s
cache = Cache(RedisBackend(client, breaker=breaker), fallback=Fallback(MemoryBackend()))
# --8<-- [end:show]
