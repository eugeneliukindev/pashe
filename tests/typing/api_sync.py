"""What the type checkers see of the sync API: read by mypy, pyright and pyrefly, never run."""

from __future__ import annotations

from typing import assert_type

from pashe import (
    Cache,
    CachedBatchFunction,
    CachedFunction,
    CachedValue,
    Locks,
    RateLimiter,
)
from pashe.backends import MemoryBackend
from pashe.locks import Lock
from pashe.ratelimit import FixedWindow, RateLimitState

cache = Cache(MemoryBackend())
locks = Locks(MemoryBackend())
limiter = RateLimiter(MemoryBackend())


@cache(ttl=60)
def get_name(user_id: int) -> str:
    return str(user_id)


@cache.value(ttl=60)
def get_rate(currency: str) -> float:
    return len(currency)


@cache.batch(ttl=60)
def get_names(user_ids: list[int]) -> dict[int, str]:
    return {user_id: str(user_id) for user_id in user_ids}


class Users:
    @cache(ttl=60)
    def name(self, user_id: int) -> str:
        return str(user_id)


@locks.locked(ttl=10)
def charge(order_id: int) -> str:
    return str(order_id)


@limiter.limited(FixedWindow(calls=5, per=60), key="logins")
def login(user_id: int) -> bool:
    return user_id > 0


# the objects of the decorators, with the signature of the function, a method bound as a function would be
cached: CachedFunction[[int], str] = get_name
unbound: CachedFunction[[Users, int], str] = Users.name
bound: CachedFunction[[int], str] = Users().name
value: CachedValue[[str], float] = get_rate
batch: CachedBatchFunction[int, str] = get_names


def check() -> None:
    # a cached function keeps the signature of the function, and its methods take the same arguments
    assert_type(get_name(1), str)
    assert_type(get_name.get(1), str | None)
    assert_type(get_name.refresh(1), str)
    assert_type(get_name.set("Ann", 1), None)
    assert_type(get_name.invalidate(1), bool)
    get_name("1")  # type: ignore[arg-type]  # the arguments of the function, checked

    # a bound method takes the arguments after self
    assert_type(Users().name(1), str)

    # a value is read and set, never called
    assert_type(get_rate.get("EUR"), float | None)
    get_rate("EUR")  # type: ignore[operator]  # a value loads nothing by itself

    # a batch takes the items and answers a dict of each
    assert_type(get_names([1, 2]), dict[int, str])
    assert_type(get_names.invalidate(1), bool)

    # the locks and the limits keep the signature of what they decorate
    assert_type(charge(1), str)
    assert_type(login(1), bool)
    charge("1")  # type: ignore[arg-type]  # the arguments of the function, checked
    assert_type(locks.lock("order:1", ttl=10), Lock)
    assert_type(locks.try_lock("order:1", ttl=10), Lock | None)
    assert_type(limiter.count("login:1", FixedWindow(calls=5, per=60)), RateLimitState | None)
