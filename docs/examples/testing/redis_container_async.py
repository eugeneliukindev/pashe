from collections.abc import Iterator

import pytest
from redis.asyncio import Redis
from testcontainers.community.redis import RedisContainer

from pashe import AsyncCache
from pashe.contrib.redis import AsyncRedisBackend


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:8-alpine") as container:
        host, port = container.get_container_host_ip(), container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


async def test_the_cache_over_redis(redis_url: str) -> None:
    async with AsyncCache(AsyncRedisBackend(Redis.from_url(redis_url))) as cache:
        await cache.ping()
