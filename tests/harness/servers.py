"""The Redis, the Redis Cluster and the memcached of the tests, in Docker: a pytest plugin that conftest loads.

Each test process starts its own of each when its first test asks for one. ``pytest --help``
lists the options under "redis".
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from testcontainers.community.redis import RedisContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import ExecWaitStrategy

from tests.harness.catalog import MEMCACHED, REDIS

if TYPE_CHECKING:
    from collections.abc import Iterator

_CLUSTER_PORTS: Final = (7000, 7001, 7002)
_MEMCACHED_PORT: Final = 11211
_CLUSTER_SCRIPT: Final = Path(__file__).with_name("cluster.sh")


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("redis", "the Redis of the tests, started in Docker")
    group.addoption(
        "--redis-server",
        choices=list(REDIS.servers),
        default=REDIS.default,
        help="the server the tests run against, and its cluster (default: %(default)s)",
    )
    group.addoption(
        "--memcached-server",
        choices=list(MEMCACHED.servers),
        default=MEMCACHED.default,
        help="the memcached the tests run against (default: %(default)s)",
    )


def pytest_report_header(config: pytest.Config) -> str:
    server = REDIS.servers[config.option.redis_server]
    memcached = MEMCACHED.servers[config.option.memcached_server].image
    return (
        f"server: {server.image}, cluster: {server.cluster_image}, memcached: {memcached}, one of each per test process"
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if isinstance(item, pytest.Function) and {"redis_url", "redis_cluster_url"} & set(item.fixturenames):
            item.add_marker(pytest.mark.redis)
        if isinstance(item, pytest.Function) and "memcached_address" in item.fixturenames:
            item.add_marker(pytest.mark.memcached)


@pytest.fixture(scope="session")
def redis_url(pytestconfig: pytest.Config) -> Iterator[str]:
    """The URL of the Redis of this test process."""
    with RedisContainer(REDIS.servers[pytestconfig.option.redis_server].image) as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(container.port)}"


@pytest.fixture(scope="session")
def redis_cluster_url(pytestconfig: pytest.Config) -> Iterator[str]:
    """The URL of one node of the Redis Cluster of this test process; its client finds the others."""
    server = REDIS.servers[pytestconfig.option.redis_server]
    arguments = [server.cluster_program, *map(str, _CLUSTER_PORTS)]
    cluster = (
        DockerContainer(server.cluster_image)
        .with_copy_into_container(_CLUSTER_SCRIPT, "/cluster.sh")
        .with_command(["sh", "/cluster.sh", "start", *arguments])
        .waiting_for(ExecWaitStrategy(["sh", "/cluster.sh", "ready", *arguments]))
    )
    with cluster as container:
        # the nodes announce the address of the container, which the bridge network of Docker routes to on Linux
        wrapped = container.get_wrapped_container()
        wrapped.reload()
        host = next(iter(wrapped.attrs["NetworkSettings"]["Networks"].values()))["IPAddress"]
        yield f"redis://{host}:{_CLUSTER_PORTS[0]}"


@pytest.fixture(scope="session")
def memcached_address(pytestconfig: pytest.Config) -> Iterator[tuple[str, int]]:
    """The host and the port of the memcached of this test process."""
    memcached = (
        DockerContainer(MEMCACHED.servers[pytestconfig.option.memcached_server].image)
        .with_exposed_ports(_MEMCACHED_PORT)
        # memcached itself answers, inside the container: the port of the host opens before it does
        .waiting_for(
            ExecWaitStrategy(["sh", "-c", f"printf 'mn\\r\\n' | nc -w 1 127.0.0.1 {_MEMCACHED_PORT} | grep -q MN"])
        )
    )
    with memcached as container:
        yield container.get_container_host_ip(), container.get_exposed_port(_MEMCACHED_PORT)
