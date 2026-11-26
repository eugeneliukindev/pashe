from collections.abc import Iterator

import pytest
from redis import Redis
from testcontainers.community.redis import RedisContainer

from pashe import Cache
from pashe.contrib.redis import RedisBackend


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:8-alpine") as container:
        host, port = container.get_container_host_ip(), container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


def test_the_cache_over_redis(redis_url: str) -> None:
    with Cache(RedisBackend(Redis.from_url(redis_url, socket_timeout=1))) as cache:
        cache.ping()
