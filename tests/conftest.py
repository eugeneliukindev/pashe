from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
from pashe._internal.sync.backends.prefixed import PrefixedBackend
from tests.harness.helpers import Clock, close, new_cache
from tests.harness.stores import SERVED, STORE_PARAMS, STORES

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from tests.harness.helpers import NewCache

pytest_plugins = ["tests.harness.servers"]  # the Redis and the Redis Cluster of the run, in Docker


@pytest.fixture(params=["sync", "async"])
def side(request: pytest.FixtureRequest) -> str:
    """Which side a test drives: Cache with def functions, or AsyncCache with async def functions."""
    return str(request.param)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def key_prefix() -> str:
    """A prefix of keys of this test alone: a cluster has one database, which test processes share."""
    return f"{uuid.uuid4().hex}:"


@pytest.fixture(params=STORE_PARAMS)
async def new_process_cache(request: pytest.FixtureRequest, side: str, key_prefix: str) -> AsyncIterator[NewCache]:
    """Make caches of the side over one store of every kind, each as a process of its own."""
    connect = STORES[request.param](request, side)
    caches: list[Any] = []

    def make(**options: Any) -> Any:
        backend = connect()
        if (
            request.param in SERVED
        ):  # the test processes share the server: keys of this test alone, the cache sees them bare
            backend = (
                PrefixedBackend(backend, key_prefix) if side == "sync" else AsyncPrefixedBackend(backend, key_prefix)
            )
        cache = new_cache(side, backend, **options)
        caches.append(cache)
        return cache

    yield make

    for cache in caches:
        await close(cache)
