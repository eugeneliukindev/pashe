"""The Redis and the Redis Cluster of a test run, in Docker: a pytest plugin that conftest loads.

The main process starts both at once and hands their URLs to the worker processes through the
input xdist gives each of them. A test that takes one of their fixtures is marked redis, so ``-m "not redis"`` runs
without Docker; so does a run that only collects.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Final

import pytest
from testcontainers.community.redis import RedisContainer
from testcontainers.core.container import DockerContainer, Reaper
from testcontainers.core.wait_strategies import ExecWaitStrategy

if TYPE_CHECKING:
    from xdist.workermanage import WorkerController

_REDIS_IMAGE: Final = "PASHE_TEST_REDIS_IMAGE"  # the server the run tests against: Redis, Valkey or Dragonfly
_DEFAULT_IMAGE: Final = "redis:8-alpine"
_REDIS_URL: Final = "PASHE_TEST_REDIS_URL"  # a Redis of your own skips the container
_REDIS_DATABASES: Final = 16  # one per test process, so processes do not flush each other; Dragonfly has 16
_CONTAINER: Final = pytest.StashKey[RedisContainer]()

_CLUSTER_URL: Final = "PASHE_TEST_REDIS_CLUSTER_URL"  # a cluster of your own skips the container
_CLUSTER_IMAGE: Final = "redis:8-alpine"
_CLUSTER_PORTS: Final = (7000, 7001, 7002)  # three primaries, so keys of different slots live on different nodes
_CLUSTER_CONTAINER: Final = pytest.StashKey[DockerContainer]()
_URLS: Final = pytest.StashKey[dict[str, str]]()  # the URL of each server, under its variable

# Three servers in one container, joined into a cluster that announces the address of the container:
# the tests reach every node there, as the bridge network of Docker is routed to the host on Linux.
_PORTS: Final = " ".join(map(str, _CLUSTER_PORTS))
_CLUSTER_SCRIPT: Final = (
    f"IP=$(hostname -i); for port in {_PORTS}; do "
    "redis-server --port $port --cluster-enabled yes --cluster-config-file /tmp/nodes-$port.conf "
    '--save "" --appendonly no --daemonize yes; done; '
    # every node answers before the cluster is made of them: a fixed sleep lost the race on a busy machine
    f"for port in {_PORTS}; do until redis-cli -p $port ping > /dev/null 2>&1; do sleep 0.1; done; done; "
    f"redis-cli --cluster create {' '.join(f'$IP:{port}' for port in _CLUSTER_PORTS)} "
    "--cluster-replicas 0 --cluster-yes > /dev/null; "
    "tail -f /dev/null"
)
# Ready once every node agrees that every slot is served.
_CLUSTER_READY: Final = (
    f"for port in {_PORTS}; do redis-cli -p $port cluster info | grep -q cluster_state:ok || exit 1; done"
)

_SERVER_FIXTURES: Final = frozenset({"redis_url", "redis_cluster_url"})
_WITHOUT_SERVERS: Final = "not redis"  # the mark expression of just test-fast


def pytest_configure(config: pytest.Config) -> None:
    if hasattr(config, "workerinput"):
        return  # a worker process: the main one started the servers
    collects_only = config.option.collectonly or config.option.deadfixtures  # just lint lists dead fixtures
    if collects_only or config.option.markexpr == _WITHOUT_SERVERS:
        return

    starts = {_REDIS_URL: _start_redis, _CLUSTER_URL: _start_cluster}
    Reaper.get_instance()  # the one cleaner of the run, before two starts race to create it
    with ThreadPoolExecutor() as starting:
        started = {
            variable: starting.submit(start, config) for variable, start in starts.items() if variable not in os.environ
        }
    urls = {variable: url for variable in starts if (url := os.environ.get(variable))}
    urls.update(
        {variable: start.result() for variable, start in started.items()}
    )  # an error of a start fails the run here
    config.stash[_URLS] = urls


def pytest_configure_node(node: WorkerController) -> None:
    urls: dict[str, str] = node.config.stash.get(_URLS, {})  # none in a run without servers
    node.workerinput.update(urls)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if isinstance(item, pytest.Function) and _SERVER_FIXTURES & set(item.fixturenames):
            item.add_marker(pytest.mark.redis)


def pytest_unconfigure(config: pytest.Config) -> None:
    for container in (config.stash.get(_CONTAINER, None), config.stash.get(_CLUSTER_CONTAINER, None)):
        if container is not None:
            container.stop()


@pytest.fixture(scope="session")
def redis_url(pytestconfig: pytest.Config, worker_id: str) -> str:
    """The URL of the Redis database of this test process."""
    database = 0 if worker_id == "master" else int(worker_id.removeprefix("gw"))
    if database >= _REDIS_DATABASES:
        msg = f"run at most {_REDIS_DATABASES} test processes: each takes a Redis database"
        raise RuntimeError(msg)
    return f"{_url(pytestconfig, _REDIS_URL)}/{database}"


@pytest.fixture(scope="session")
def redis_cluster_url(pytestconfig: pytest.Config) -> str:
    """The URL of one node of the Redis Cluster of the run; its client finds the others."""
    return _url(pytestconfig, _CLUSTER_URL)


def _url(config: pytest.Config, variable: str) -> str:
    urls: dict[str, str] = getattr(config, "workerinput", None) or config.stash[_URLS]  # a worker or the main process
    return urls[variable]


def _start_redis(config: pytest.Config) -> str:
    image = os.environ.get(_REDIS_IMAGE, _DEFAULT_IMAGE)
    if "dragonfly" in image:
        command = f"--dbnum={_REDIS_DATABASES}"
    else:
        command = f"{'valkey-server' if 'valkey' in image else 'redis-server'} --databases {_REDIS_DATABASES}"
    container = RedisContainer(image).with_command(command).start()
    config.stash[_CONTAINER] = container

    host, port = container.get_container_host_ip(), container.get_exposed_port(container.port)
    return f"redis://{host}:{port}"


def _start_cluster(config: pytest.Config) -> str:
    container = DockerContainer(_CLUSTER_IMAGE).with_command(["sh", "-c", _CLUSTER_SCRIPT])
    container.waiting_for(ExecWaitStrategy(["sh", "-c", _CLUSTER_READY])).start()
    config.stash[_CLUSTER_CONTAINER] = container

    wrapped = container.get_wrapped_container()
    wrapped.reload()
    host = next(iter(wrapped.attrs["NetworkSettings"]["Networks"].values()))["IPAddress"]
    return f"redis://{host}:{_CLUSTER_PORTS[0]}"
