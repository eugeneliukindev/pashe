"""The calls to the backend each operation makes, as docs/deep-dive/cost.md tells them."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, override

import pytest

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede
from pashe.ratelimit import FixedWindow, SlidingWindow

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


class _Counting(MemoryBackend):
    """A memory backend that counts its calls by name: each is one round trip to Redis."""

    def __init__(self) -> None:
        super().__init__()

        self.calls: Counter[str] = Counter()

    @override
    def get(self, key: str, /) -> bytes | None:
        self.calls["get"] += 1
        return super().get(key)

    @override
    def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        self.calls["get_many"] += 1
        return super().get_many(keys)

    @override
    def set(self, key: str, value: bytes, /, *, ttl: float | None = None) -> None:
        self.calls["set"] += 1
        super().set(key, value, ttl=ttl)

    @override
    def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        self.calls["set_many"] += 1
        super().set_many(values, ttl=ttl)

    @override
    def set_if_absent(self, key: str, value: bytes, /, *, ttl: float | None = None) -> bool:
        self.calls["set_if_absent"] += 1
        return super().set_if_absent(key, value, ttl=ttl)

    @override
    def delete(self, key: str, /) -> bool:
        self.calls["delete"] += 1
        return super().delete(key)

    @override
    def incr(self, key: str, by: int, /, *, ttl: float | None = None) -> int:
        self.calls["incr"] += 1
        return super().incr(key, by, ttl=ttl)

    @override
    def ttl(self, key: str, /) -> float | None:
        self.calls["ttl"] += 1
        return super().ttl(key)

    @override
    def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        self.calls["delete_if_equals"] += 1
        return super().delete_if_equals(key, value)


def _plain(cache: Cache) -> Callable[[], object]:
    @cache(ttl=60, key="user:1")
    def get_user() -> int:
        return 1

    return get_user


def _tagged(cache: Cache) -> Callable[[], object]:
    @cache(ttl=60, key="user:1", tags=["user:1", "team:7"])
    def get_user() -> int:
        return 1

    return get_user


def _locked(cache: Cache) -> Callable[[], object]:
    @cache(ttl=60, key="user:1", stampede=Stampede(lock_for=5))
    def get_user() -> int:
        return 1

    return get_user


@pytest.mark.parametrize(
    ("make", "warm", "calls"),
    [
        (_plain, False, {"get": 1, "set": 1}),
        (_plain, True, {"get": 1}),
        (_tagged, False, {"get_many": 1, "set_if_absent": 2, "set": 1}),
        (_tagged, True, {"get_many": 1}),
        (_locked, False, {"get": 2, "set_if_absent": 1, "set": 1, "delete_if_equals": 1}),
    ],
    ids=["miss", "hit", "miss with 2 new tags", "hit with 2 tags", "miss under lock_for"],
)
def test_a_cached_call_makes_the_calls_the_page_tells(
    make: Callable[[Cache], Callable[[], object]], *, warm: bool, calls: dict[str, int]
) -> None:
    backend = _Counting()
    get_user = make(Cache(backend))
    if warm:
        get_user()
        backend.calls.clear()

    get_user()

    assert backend.calls == calls


@pytest.mark.parametrize(
    ("operation", "calls"),
    [
        (lambda cache: cache.invalidate_tags("user:1", "team:7"), {"set_if_absent": 2, "incr": 2}),
        (lambda cache: cache.rate_limit("ip", SlidingWindow(calls=10, per=60)), {"incr": 1, "get": 1}),
        (lambda cache: cache.rate_limit("ip", FixedWindow(calls=10, per=60)), {"incr": 1, "ttl": 1}),
        (lambda cache: cache.try_lock("job", ttl=30), {"set_if_absent": 1}),
    ],
    ids=["invalidate 2 tags", "sliding window", "fixed window", "try_lock"],
)
def test_an_operation_makes_the_calls_the_page_tells(
    operation: Callable[[Cache], object], calls: dict[str, int]
) -> None:
    backend = _Counting()

    operation(Cache(backend))

    assert backend.calls == calls


def test_a_lock_block_takes_and_releases_in_two_calls() -> None:
    backend = _Counting()
    cache = Cache(backend)

    with cache.lock("job", ttl=30):
        pass

    assert backend.calls == {"set_if_absent": 1, "delete_if_equals": 1}
