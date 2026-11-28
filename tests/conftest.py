from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from tests.harness.helpers import SIDES, Clock, close
from tests.harness.stores import SERVED, STORE_PARAMS, STORES

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from tests.harness.helpers import (
        EitherBackend,
        EitherCache,
        EitherLimiter,
        EitherLocks,
        NewCache,
        NewLimiter,
        NewLocks,
        Side,
    )

pytest_plugins = ["tests.harness.servers"]


@pytest.fixture(params=list(SIDES))
def side(request: pytest.FixtureRequest) -> Side:
    """Which side a test drives: Cache with def functions, or AsyncCache with async def functions.

    A test of one side alone narrows it by name: ``@pytest.mark.parametrize("side", ["async"], indirect=True)``.
    """
    return SIDES[request.param]


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def key_prefix() -> str:
    """A prefix of keys of this test alone: a cluster has one database, which test processes share."""
    return f"{uuid.uuid4().hex}:"


@pytest.fixture(params=STORE_PARAMS)
async def new_process_cache(
    request: pytest.FixtureRequest,
    side: Side,
    key_prefix: str,
) -> AsyncIterator[NewCache]:
    """Make caches of the side over one store of every kind, each as a process of its own."""
    connect = STORES[request.param](request, side)
    caches: list[EitherCache] = []

    def make(**options: object) -> EitherCache:
        backend = connect()
        if request.param in SERVED:  # the tests share the server: keys of this test alone, the cache sees them bare
            backend = side.prefixed(backend, key_prefix)
        cache = side.new_cache(backend, **options)
        caches.append(cache)
        return cache

    yield make

    for cache in caches:
        await close(cache)


@pytest.fixture(params=STORE_PARAMS)
async def new_process_locks(
    request: pytest.FixtureRequest,
    side: Side,
    key_prefix: str,
) -> AsyncIterator[NewLocks]:
    """Make the locks of the side over one store of every kind, each as a process of its own."""
    connect = STORES[request.param](request, side)
    backends: list[EitherBackend] = []

    def make(**options: object) -> EitherLocks:
        backend = connect()
        backends.append(backend)
        if request.param in SERVED:  # the tests share the server: keys of this test alone
            backend = side.prefixed(backend, key_prefix)
        return side.new_locks(backend, **options)

    yield make

    for backend in backends:  # the locks close nothing: the backend is the test's
        await close(backend)


@pytest.fixture(params=STORE_PARAMS)
async def new_process_limiter(
    request: pytest.FixtureRequest,
    side: Side,
    key_prefix: str,
) -> AsyncIterator[NewLimiter]:
    """Make rate limiters of the side over one store of every kind, each as a process of its own."""
    connect = STORES[request.param](request, side)
    backends: list[EitherBackend] = []

    def make(**options: object) -> EitherLimiter:
        backend = connect()
        backends.append(backend)
        if request.param in SERVED:  # the tests share the server: keys of this test alone
            backend = side.prefixed(backend, key_prefix)
        return side.new_limiter(backend, **options)

    yield make

    for backend in backends:  # the limiter closes nothing: the backend is the test's
        await close(backend)
