"""The Redis and the Redis Cluster of the tests, in Docker: a pytest plugin that conftest loads.

Each test process starts its own Redis and cluster when its first test asks for one. ``pytest --help``
lists the options under "redis".
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, get_args

import pytest
from testcontainers.community.redis import RedisContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import ExecWaitStrategy

if TYPE_CHECKING:
    from collections.abc import Iterator

type _ClusterProgram = Literal["redis", "valkey"]


@dataclass(frozen=True, slots=True, kw_only=True)
class _Server:
    image: str
    cluster_image: str
    cluster_program: _ClusterProgram

    def __post_init__(self) -> None:
        if self.cluster_program not in get_args(_ClusterProgram.__value__):
            msg = f"servers.toml: the cluster_program of {self.image} is {self.cluster_program!r}, not redis or valkey"
            raise ValueError(msg)


_CATALOG: Final = tomllib.loads(Path(__file__).with_name("servers.toml").read_text())
_SERVERS: Final = {name: _Server(**server) for name, server in _CATALOG["servers"].items()}
_DEFAULT_SERVER: Final[str] = _CATALOG["default"]

_CLUSTER_PORTS: Final = (7000, 7001, 7002)
_CLUSTER_SCRIPT: Final = Path(__file__).with_name("cluster.sh")


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("redis", "the Redis of the tests, started in Docker")
    group.addoption(
        "--redis-server",
        choices=list(_SERVERS),
        default=_DEFAULT_SERVER,
        help="the server the tests run against, and its cluster (default: %(default)s)",
    )


def pytest_report_header(config: pytest.Config) -> str:
    server = _SERVERS[config.option.redis_server]
    return f"server: {server.image}, cluster: {server.cluster_image}, one of each per test process"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if isinstance(item, pytest.Function) and {"redis_url", "redis_cluster_url"} & set(item.fixturenames):
            item.add_marker(pytest.mark.redis)


@pytest.fixture(scope="session")
def redis_url(pytestconfig: pytest.Config) -> Iterator[str]:
    """The URL of the Redis of this test process."""
    with RedisContainer(_SERVERS[pytestconfig.option.redis_server].image) as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(container.port)}"


@pytest.fixture(scope="session")
def redis_cluster_url(pytestconfig: pytest.Config) -> Iterator[str]:
    """The URL of one node of the Redis Cluster of this test process; its client finds the others."""
    server = _SERVERS[pytestconfig.option.redis_server]
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
