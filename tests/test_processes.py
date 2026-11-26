"""Caches that stand for processes of their own over one store: memory, a Redis and a cluster.

The few scenarios every part of a cache meets its store in: entries, tag counters, batches, locks and
counters of rate limits. On a cluster their keys fall on several nodes, so one call reads from more
than one of them.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from pashe import AsyncCache
from pashe.compressors import GzipCompressor
from pashe.errors import NotFoundError, RateLimitedError
from pashe.options import Negative, Stale, Stampede
from pashe.ratelimit import FixedWindow, per_minute
from tests.harness.helpers import Source, batch_function, cached_function, call, close, run_block

if TYPE_CHECKING:
    from pashe import AsyncCachedFunction
    from tests.harness.helpers import Clock, EitherCache, NewCache


class UserNotFoundError(LookupError):
    pass


# EntryCodec


async def test_a_second_call_is_answered_from_the_cache(new_process_cache: NewCache) -> None:
    source = Source()
    get_user = cached_function(new_process_cache(), source, ttl=60, key="user:{user_id}")

    first = await call(get_user, 1)
    second = await call(get_user, 1)

    assert first == second == {"id": 1, "version": 1}
    assert source.calls == 1


async def test_a_result_set_in_one_process_answers_in_another(new_process_cache: NewCache) -> None:
    writer, reader = Source(), Source()
    set_user = cached_function(new_process_cache(), writer, ttl=60, key="user:{user_id}")
    get_user = cached_function(new_process_cache(), reader, ttl=60, key="user:{user_id}")

    await call(set_user.set, {"id": 1, "version": 7}, 1)
    user = await call(get_user, 1)

    assert user == {"id": 1, "version": 7}
    assert reader.calls == 0


async def test_invalidate_drops_the_result_for_every_process(new_process_cache: NewCache) -> None:
    source = Source()
    get_user = cached_function(new_process_cache(), source, ttl=60, key="user:{user_id}")
    drop_user = cached_function(new_process_cache(), Source(), ttl=60, key="user:{user_id}")
    await call(get_user, 1)

    removed = await call(drop_user.invalidate, 1)
    await call(get_user, 1)

    assert removed
    assert source.calls == 2


async def test_negative_caching_keeps_a_not_found(new_process_cache: NewCache) -> None:
    source = Source()
    source.error = UserNotFoundError()
    negative = Negative(on=(UserNotFoundError,), ttl=30)
    get_user = cached_function(new_process_cache(), source, ttl=60, negative=negative)

    for _ in range(2):
        with pytest.raises(NotFoundError):
            await call(get_user, 1)

    assert source.calls == 1


async def test_stale_while_revalidate_reloads_in_the_background(new_process_cache: NewCache, clock: Clock) -> None:
    cache = new_process_cache(clock=clock)
    source = Source()
    get_user = cached_function(cache, source, ttl=60, stale=Stale(while_revalidate=600))
    await call(get_user, 1)
    clock.now += 61
    source.version = 2

    stale = await call(get_user, 1)
    await close(cache)

    assert stale == {"id": 1, "version": 1}
    assert source.calls == 2


async def test_a_compressed_result_answers_in_another_process(new_process_cache: NewCache) -> None:
    writer, reader = Source(), Source()
    set_user = cached_function(new_process_cache(compressor=GzipCompressor()), writer, ttl=60)
    get_user = cached_function(new_process_cache(compressor=GzipCompressor()), reader, ttl=60)

    await call(set_user.set, {"id": 1, "version": 7}, 1)
    user = await call(get_user, 1)

    assert user == {"id": 1, "version": 7}
    assert reader.calls == 0


# Tags


async def test_an_invalidation_reaches_every_process(new_process_cache: NewCache) -> None:
    source = Source()
    tags = ["users", "user:{user_id}", "team:admins", "region:eu"]  # counters on more than one node of a cluster
    get_user = cached_function(new_process_cache(), source, ttl=60, key="user:{user_id}", tags=tags)
    await call(get_user, 1)
    await call(get_user, 2)

    await call(new_process_cache().invalidate_tags, "user:1")
    await call(get_user, 1)
    await call(get_user, 2)

    assert source.calls == 3  # user 1 again, user 2 still cached


async def test_every_invalidation_of_a_tag_takes_effect(new_process_cache: NewCache) -> None:
    # A counter starts at a random 62-bit integer: past those a float, or Lua, keeps exactly.
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, tags=["users"])
    await call(get_user, 1)
    await call(cache.invalidate_tags, "users")
    await call(get_user, 1)

    await call(cache.invalidate_tags, "users")
    await call(get_user, 1)

    assert source.calls == 3


# Batches


async def test_a_batch_loads_only_the_missing_items(new_process_cache: NewCache) -> None:
    asked: list[list[int]] = []
    get_items = batch_function(new_process_cache(), asked)
    await call(get_items, [1, 2, 3])

    items = await call(get_items, [2, 3, 4, 5])

    assert items == {2: 20, 3: 30, 4: 40, 5: 50}
    assert asked == [[1, 2, 3], [4, 5]]


# Locks and rate limits


@pytest.mark.parametrize("side", ["async"], indirect=True)  # the processes of this test are tasks of one event loop
async def test_lock_for_loads_once_for_all_processes(new_process_cache: NewCache) -> None:
    loads = 0

    def cached(cache: EitherCache) -> AsyncCachedFunction[[int], int]:
        assert isinstance(cache, AsyncCache)

        @cache(ttl=60, key="user:{user_id}", stampede=Stampede(lock_for=5))
        async def get_user(user_id: int) -> int:
            nonlocal loads
            loads += 1
            await asyncio.sleep(0.05)
            return user_id

        return get_user

    first, second = cached(new_process_cache()), cached(new_process_cache())

    users = await asyncio.gather(first(1), second(1))

    assert list(users) == [1, 1]
    assert loads == 1


async def test_a_lock_held_by_one_process_is_busy_for_another(new_process_cache: NewCache) -> None:
    holder, other = new_process_cache(), new_process_cache()
    await call(holder.try_lock, "job", ttl=5)

    lock = await call(other.try_lock, "job", ttl=5)

    assert lock is None


async def test_a_lock_released_by_one_process_is_free_for_another(new_process_cache: NewCache) -> None:
    holder, other = new_process_cache(), new_process_cache()
    lock = await call(holder.try_lock, "job", ttl=5)
    assert lock is not None

    await run_block(lock)

    assert await call(other.try_lock, "job", ttl=5) is not None


async def test_a_rate_limit_counts_the_calls_of_every_process(new_process_cache: NewCache) -> None:
    first, second = new_process_cache(), new_process_cache()
    await call(first.rate_limit, "ip", per_minute(2))
    await call(second.rate_limit, "ip", per_minute(2))

    with pytest.raises(RateLimitedError):
        await call(first.rate_limit, "ip", per_minute(2))


async def test_a_fixed_window_bans_the_calls_of_every_process(new_process_cache: NewCache) -> None:
    first, second = new_process_cache(), new_process_cache()
    limit = FixedWindow(calls=1, per=60, ban_for=120)
    await call(first.rate_limit, "ip", limit)

    with pytest.raises(RateLimitedError) as refused:
        await call(second.rate_limit, "ip", limit)

    assert refused.value.retry_after == 120
