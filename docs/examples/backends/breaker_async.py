# --8<-- [start:show]
import redis.asyncio

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend, CircuitBreaker
from pashe.contrib.redis import AsyncRedisBackend
from pashe.options import Fallback

client = redis.asyncio.Redis.from_url(
    "redis://localhost:6379/0",
    socket_connect_timeout=0.1,  # a Redis that is down costs 0.1 s, not the default wait
    socket_timeout=0.2,
)
breaker = CircuitBreaker(failure_threshold=5, open_for=10)  # 5 failures in a row: skip Redis for 10 s
cache = AsyncCache(AsyncRedisBackend(client, breaker=breaker), fallback=Fallback(AsyncMemoryBackend()))
# --8<-- [end:show]
