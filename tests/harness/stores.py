"""The stores the tests run over, and how a test reaches one: a new store is one more entry here.

A store gets the request of the test, for the URL of its server, and the side, and gives how
to connect a process to it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster
from redis.cluster import RedisCluster

from pashe.backends import AsyncSQLiteBackend, SQLiteBackend
from pashe.contrib.redis import AsyncRedisBackend, RedisBackend
from tests.harness.helpers import memory

if TYPE_CHECKING:
    from collections.abc import Callable

    type Connect = Callable[[], Any]  # makes a backend of the side over the store, with a client of its own


def _memory(_request: pytest.FixtureRequest, side: str) -> Connect:
    shared = memory(side)
    return lambda: shared  # the processes of a test share the memory, as they share a server


def _sqlite(request: pytest.FixtureRequest, side: str) -> Connect:
    path = request.getfixturevalue("tmp_path") / "cache.db"  # every process of a test opens the one file
    if side == "sync":
        return lambda: SQLiteBackend(path)
    return lambda: AsyncSQLiteBackend(path)


def _redis(request: pytest.FixtureRequest, side: str) -> Connect:
    url = request.getfixturevalue("redis_url")
    if side == "sync":
        return lambda: RedisBackend(Redis.from_url(url))
    return lambda: AsyncRedisBackend(AsyncRedis.from_url(url))


def _cluster(request: pytest.FixtureRequest, side: str) -> Connect:
    url = request.getfixturevalue("redis_cluster_url")
    if side == "sync":
        return lambda: RedisBackend(RedisCluster.from_url(url))
    return lambda: AsyncRedisBackend(AsyncRedisCluster.from_url(url))


IN_PROCESS: Final = {"memory": _memory, "sqlite": _sqlite}  # sqlite: a file, no server
SERVED: Final = {"redis": _redis, "cluster": _cluster}  # each needs its server, so -m "not redis" leaves it out
STORES: Final = IN_PROCESS | SERVED
STORE_PARAMS: Final = [*IN_PROCESS, *(pytest.param(name, marks=pytest.mark.redis) for name in SERVED)]
