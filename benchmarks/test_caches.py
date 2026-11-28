from __future__ import annotations

import itertools
import uuid
from typing import TYPE_CHECKING, TypedDict

import pytest
from tests.harness.helpers import SYNC
from tests.harness.stores import STORE_PARAMS, STORES

from pashe import Cache

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_benchmark.fixture import BenchmarkFixture


class User(TypedDict):
    id: int
    name: str


@pytest.fixture(params=STORE_PARAMS)
def cache(request: pytest.FixtureRequest) -> Iterator[Cache]:
    """A cache over each store the tests run over, as a service of one process would run it."""
    connect = STORES[request.param](request, SYNC)
    opened = SYNC.new_cache(connect(), prefix=f"{uuid.uuid4().hex}:")  # the keys of this run alone
    assert isinstance(opened, Cache)
    yield opened
    opened.close()


def test_a_hit(cache: Cache, benchmark: BenchmarkFixture) -> None:
    @cache(ttl=300)
    def get_user(user_id: int) -> User:
        return User(id=user_id, name="Ann")

    get_user(1)
    benchmark.group = "caches: a call answered from the cache"

    answered = benchmark(get_user, 1)

    assert answered == User(id=1, name="Ann")


def test_a_miss(cache: Cache, benchmark: BenchmarkFixture) -> None:
    @cache(ttl=300)
    def get_user(user_id: int) -> User:
        return User(id=user_id, name="Ann")

    users = itertools.count()  # a new key every call: it loads and stores
    benchmark.group = "caches: a call that loads and stores"

    answered = benchmark(lambda: get_user(next(users)))

    assert answered["name"] == "Ann"
