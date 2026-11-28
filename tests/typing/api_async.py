"""What the type checkers see of the async API: read by mypy, pyright and pyrefly, never run."""

from __future__ import annotations

from typing import assert_type

from pashe import (
    AsyncCache,
    AsyncCachedBatchFunction,
    AsyncCachedFunction,
    AsyncCachedValue,
    AsyncLocks,
    AsyncRateLimiter,
)
from pashe.backends import AsyncMemoryBackend
from pashe.locks import AsyncLock
from pashe.ratelimit import FixedWindow, RateLimitState

cache = AsyncCache(AsyncMemoryBackend())
locks = AsyncLocks(AsyncMemoryBackend())
limiter = AsyncRateLimiter(AsyncMemoryBackend())


@cache(ttl=60)
async def get_name(user_id: int) -> str:
    return str(user_id)


@cache.value(ttl=60)
async def get_rate(currency: str) -> float:
    return len(currency)


@cache.batch(ttl=60)
async def get_names(user_ids: list[int]) -> dict[int, str]:
    return {user_id: str(user_id) for user_id in user_ids}


class Users:
    @cache(ttl=60)
    async def name(self, user_id: int) -> str:
        return str(user_id)


@locks.locked(ttl=10)
async def charge(order_id: int) -> str:
    return str(order_id)


@limiter.limited(FixedWindow(calls=5, per=60), key="logins")
async def login(user_id: int) -> bool:
    return user_id > 0


# the objects of the decorators, with the signature of the function, a method bound as a function would be
cached: AsyncCachedFunction[[int], str] = get_name
unbound: AsyncCachedFunction[[Users, int], str] = Users.name
bound: AsyncCachedFunction[[int], str] = Users().name
value: AsyncCachedValue[[str], float] = get_rate
batch: AsyncCachedBatchFunction[int, str] = get_names


async def check() -> None:
    # a cached function keeps the signature of the function, and its methods take the same arguments
    assert_type(await get_name(1), str)
    assert_type(await get_name.get(1), str | None)
    assert_type(await get_name.refresh(1), str)
    assert_type(await get_name.set("Ann", 1), None)
    assert_type(await get_name.invalidate(1), bool)
    await get_name("1")  # type: ignore[arg-type]  # the arguments of the function, checked

    # a bound method takes the arguments after self
    assert_type(await Users().name(1), str)

    # a value is read and set, never called
    assert_type(await get_rate.get("EUR"), float | None)
    await get_rate("EUR")  # type: ignore[operator]  # a value loads nothing by itself

    # a batch takes the items and answers a dict of each
    assert_type(await get_names([1, 2]), dict[int, str])
    assert_type(await get_names.invalidate(1), bool)

    # the locks and the limits keep the signature of what they decorate
    assert_type(await charge(1), str)
    assert_type(await login(1), bool)
    await charge("1")  # type: ignore[arg-type]  # the arguments of the function, checked
    assert_type(locks.lock("order:1", ttl=10), AsyncLock)
    assert_type(await locks.try_lock("order:1", ttl=10), AsyncLock | None)
    assert_type(await limiter.count("login:1", FixedWindow(calls=5, per=60)), RateLimitState | None)


@cache(ttl=60)  # type: ignore[arg-type]  # the async cache refuses a sync function
def sync_name(user_id: int) -> str:
    return str(user_id)
