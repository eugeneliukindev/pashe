from redis import Redis

from pashe.contrib.redis import RedisBackend

backend = RedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1))
