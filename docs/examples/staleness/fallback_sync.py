from redis import Redis

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.redis import RedisBackend
from pashe.options import Fallback

cache = Cache(RedisBackend(Redis.from_url("redis://localhost:6379/0")), fallback=Fallback(MemoryBackend(), ttl=30))
