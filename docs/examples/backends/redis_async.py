from redis.asyncio import Redis

from pashe.contrib.redis import AsyncRedisBackend

backend = AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0", socket_timeout=1))
