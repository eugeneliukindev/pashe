from redis import Redis

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.redis import RedisBackend

cache = Cache(RedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1)), prefix="app:")
test_cache = Cache(MemoryBackend())
