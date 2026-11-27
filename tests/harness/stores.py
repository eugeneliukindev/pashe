"""The stores the tests run over, and how a test reaches one: a new store is one more entry here.

A store gets the request of the test, for the URL of its server, and the side, and gives how
to connect a process to it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.harness.helpers import EitherBackend, Side

    type Connect = Callable[[], EitherBackend]  # makes a backend of the side over the store, with a client of its own
    type Store = Callable[[pytest.FixtureRequest, Side], Connect]


def _memory(_request: pytest.FixtureRequest, side: Side) -> Connect:
    shared = side.memory()
    return lambda: shared  # the processes of a test share the memory, as they share a server


def _sqlite(request: pytest.FixtureRequest, side: Side) -> Connect:
    tmp_path: Path = request.getfixturevalue("tmp_path")
    return lambda: side.sqlite(tmp_path / "cache.db")  # every process of a test opens the one file


def _redis(request: pytest.FixtureRequest, side: Side) -> Connect:
    url: str = request.getfixturevalue("redis_url")
    return lambda: side.redis(url)


def _cluster(request: pytest.FixtureRequest, side: Side) -> Connect:
    url: str = request.getfixturevalue("redis_cluster_url")
    return lambda: side.redis_cluster(url)


def _memcached(request: pytest.FixtureRequest, side: Side) -> Connect:
    host, port = request.getfixturevalue("memcached_address")
    return lambda: side.memcached(host, port)


IN_PROCESS: Final[dict[str, Store]] = {"memory": _memory, "sqlite": _sqlite}
SERVED: Final[dict[str, Store]] = {
    "redis": _redis,
    "cluster": _cluster,
    "memcached": _memcached,
}  # each needs its server, so -m "not redis and not memcached" leaves it out
STORES: Final = IN_PROCESS | SERVED
STORE_PARAMS: Final = [
    *(pytest.param(name) for name in IN_PROCESS),
    *(pytest.param(name, marks=pytest.mark.memcached if name == "memcached" else pytest.mark.redis) for name in SERVED),
]
