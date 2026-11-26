"""Cached functions on both sides: when a stored result answers and when the loader runs."""

from __future__ import annotations

import asyncio
import enum
import functools
import logging
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, override

import pytest

import pashe
from pashe import AsyncCache, Cache
from pashe.backends import AsyncMemoryBackend, MemoryBackend
from pashe.compressors import Compressor, GzipCompressor
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.errors import BackendError, InvalidOptionsError, NotFoundError
from pashe.hooks import CacheStatus, LoggingHook, Operation
from pashe.options import Fallback, IfError, IfSlow, Negative, Stale, Stampede, Store
from pashe.ratelimit import per_second
from tests.harness.helpers import (
    LOOP_BLOCK_SECONDS,
    SYNC,
    FailingMemoryBackend,
    RecordingHook,
    Source,
    batch_function,
    cached_function,
    call,
    close,
    json_codecs,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from pashe import AsyncCachedFunction, AsyncCachedValue, CachedFunction, CachedValue
    from pashe.codecs import Codec
    from pashe.hooks import Failure, Outcome
    from tests.harness.helpers import Clock, EitherCache, NewCache, Side


class UserNotFoundError(LookupError):
    pass


def results(outcomes: list[Outcome]) -> list[CacheStatus]:
    return [outcome.status for outcome in outcomes]


# Hits and the TTL


async def test_a_second_call_is_answered_from_the_cache(new_process_cache: NewCache) -> None:
    outcomes: list[Outcome] = []
    cache = new_process_cache(hooks=[RecordingHook(outcomes=outcomes)])
    source = Source()
    get_user = cached_function(cache, source, ttl=60, key="user:{user_id}")

    first = await call(get_user, 42)
    second = await call(get_user, 42)

    assert first == second == {"id": 42, "version": 1}
    assert source.calls == 1
    assert results(outcomes) == [CacheStatus.MISS, CacheStatus.HIT]
    assert outcomes[0].key == "user:42"


async def test_other_arguments_load_results_of_their_own(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60)

    users = [await call(get_user, 1), await call(get_user, 2)]

    assert users == [{"id": 1, "version": 1}, {"id": 2, "version": 1}]
    assert source.calls == 2


@pytest.mark.parametrize("ttl", [90, 90.0, timedelta(seconds=90)])
@pytest.mark.parametrize(("elapsed", "loads"), [(89, 1), (91, 2)])
async def test_a_result_answers_until_its_ttl_ends(
    new_process_cache: NewCache,
    clock: Clock,
    ttl: object,
    elapsed: float,
    loads: int,
) -> None:
    cache = new_process_cache(clock=clock)
    source = Source()
    get_user = cached_function(cache, source, ttl=ttl)
    await call(get_user, 1)

    clock.now += elapsed
    await call(get_user, 1)

    assert source.calls == loads


@pytest.mark.parametrize(("elapsed", "loads"), [(4, 1), (6, 2)])
async def test_a_ttl_from_the_result(
    new_process_cache: NewCache,
    clock: Clock,
    elapsed: float,
    loads: int,
) -> None:
    cache = new_process_cache(clock=clock)
    source = Source()
    get_user = cached_function(cache, source, ttl=lambda user: timedelta(seconds=5 * user["version"]))
    await call(get_user, 1)

    clock.now += elapsed
    await call(get_user, 1)

    assert source.calls == loads


async def test_a_negative_ttl_from_the_result_is_not_stored_and_reported(new_process_cache: NewCache) -> None:
    failures: list[Failure] = []
    cache = new_process_cache(hooks=[RecordingHook(failures=failures)])
    source = Source()
    get_user = cached_function(cache, source, ttl=lambda _user: -1)

    await call(get_user, 1)
    await call(get_user, 1)

    assert source.calls == 2
    assert [type(failure.error) for failure in failures] == [InvalidOptionsError, InvalidOptionsError]


# set, refresh and invalidate


async def test_set_stores_a_result_without_loading(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60)

    await call(get_user.set, {"id": 1, "version": 7}, 1)

    assert await call(get_user, 1) == {"id": 1, "version": 7}
    assert source.calls == 0


async def test_refresh_loads_and_stores_whatever_is_stored(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60)
    await call(get_user, 1)
    source.version = 3

    refreshed = await call(get_user.refresh, 1)

    assert refreshed == {"id": 1, "version": 3}
    assert await call(get_user, 1) == {"id": 1, "version": 3}
    assert source.calls == 2


async def test_a_refresh_the_policy_does_not_store_drops_the_old_result(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, store=Store(when=lambda user: user["version"] == 1))
    await call(get_user, 1)
    source.version = 2

    await call(get_user.refresh, 1)

    assert await call(get_user, 1) == {"id": 1, "version": 2}
    assert source.calls == 3


async def test_invalidate_drops_the_result(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60)
    await call(get_user, 1)

    removed = await call(get_user.invalidate, 1)

    assert removed
    await call(get_user, 1)
    assert source.calls == 2


async def test_invalidate_of_a_missing_result_answers_false(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    get_user = cached_function(cache, Source(), ttl=60)

    removed = await call(get_user.invalidate, 1)

    assert not removed


# Tags


async def test_invalidating_a_tag_makes_its_results_load_again(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, tags=["users"])
    await call(get_user, 1)

    await call(cache.invalidate_tags, "users")
    await call(get_user, 1)

    assert source.calls == 2


async def test_invalidating_a_tag_leaves_the_results_of_other_tags(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    users, orders = Source(), Source()
    get_user = cached_function(cache, users, ttl=60, key="user:{user_id}", tags=["users"])
    get_order = cached_function(cache, orders, ttl=60, key="order:{user_id}", tags=["orders"])
    await call(get_user, 1)
    await call(get_order, 1)

    await call(cache.invalidate_tags, "users")
    await call(get_user, 1)
    await call(get_order, 1)

    assert (users.calls, orders.calls) == (2, 1)


async def test_a_tag_template_names_a_tag_per_call(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, tags=["user:{user_id}"])
    await call(get_user, 1)
    await call(get_user, 2)

    await call(cache.invalidate_tags, "user:1")
    await call(get_user, 1)
    await call(get_user, 2)

    assert source.calls == 3  # user 1 again, user 2 still cached


async def test_every_invalidation_of_a_tag_takes_effect(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, tags=["users"])
    await call(get_user, 1)
    await call(cache.invalidate_tags, "users")
    await call(get_user, 1)

    await call(cache.invalidate_tags, "users")
    await call(get_user, 1)

    assert source.calls == 3


async def test_a_tag_invalidated_before_any_result_still_caches(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, tags=["users"])
    await call(cache.invalidate_tags, "users")

    await call(get_user, 1)
    await call(get_user, 1)

    assert source.calls == 1


async def test_an_invalidation_reaches_every_process(side: Side) -> None:
    backend = side.memory()
    reader, writer = side.new_cache(backend), side.new_cache(backend)
    source = Source()
    get_user = cached_function(reader, source, ttl=60, tags=["users"])
    await call(get_user, 1)

    await call(writer.invalidate_tags, "users")
    await call(get_user, 1)

    assert source.calls == 2


def _rename(
    cache: EitherCache,
    side: Side,
    error: Exception | None = None,
) -> Callable[[int], object]:
    """Return a write of user_id of the side that invalidates its tag, and raises error if one is given."""

    def write(user_id: int) -> None:  # noqa: ARG001 - the tag is filled from it
        if error is not None:
            raise error

    return cache.invalidates(tags=["user:{user_id}"])(side.function(write))


async def test_invalidates_drops_the_results_of_its_tags_after_a_write(side: Side, new_process_cache: NewCache) -> None:
    cache, source = new_process_cache(), Source()
    get_user = cached_function(cache, source, ttl=60, tags=["user:{user_id}"])
    await call(get_user, 1)
    await call(get_user, 2)

    await call(_rename(cache, side), 1)
    await call(get_user, 1)
    await call(get_user, 2)

    assert source.calls == 3  # user 1 again, user 2 still cached


async def test_invalidates_drops_them_after_a_write_that_raised_too(side: Side, new_process_cache: NewCache) -> None:
    cache, source = new_process_cache(), Source()
    get_user = cached_function(cache, source, ttl=60, tags=["user:{user_id}"])
    await call(get_user, 1)

    with pytest.raises(ValueError, match="half written"):
        await call(_rename(cache, side, ValueError("half written")), 1)
    await call(get_user, 1)

    assert source.calls == 2


async def test_invalidates_hands_a_failing_backend_to_the_hooks_and_returns(side: Side) -> None:
    failures: list[Failure] = []
    backend = side.failing_memory()
    rename = _rename(side.new_cache(backend, hooks=[RecordingHook(failures=failures)]), side)
    backend.down = True

    await call(rename, 1)

    assert [(failure.operation, failure.key) for failure in failures] == [(Operation.INVALIDATE, "user:1")]


def test_invalidates_refuses_a_template_of_no_parameter() -> None:
    cache = Cache(MemoryBackend())

    with pytest.raises(InvalidOptionsError, match=r"names \{team_id\}"):
        cache.invalidates(tags=["team:{team_id}"])(lambda user_id: user_id)


# Values


def _login_code(
    cache: EitherCache,
    side: Side,
    **options: object,
) -> CachedValue[[str, int], str] | AsyncCachedValue[[str, int], str]:
    """Return a value of the side: the one-time code of an email, tagged with its user."""
    declare = cache.value(ttl=600, key="otp:{email}", tags=["user:{user_id}"], **options)

    def login_code(email: str, user_id: int) -> str:
        raise NotImplementedError

    return declare(side.function(login_code))


async def test_a_value_is_what_was_set_and_none_before(side: Side, new_process_cache: NewCache) -> None:
    code = _login_code(new_process_cache(), side)
    before = await call(code.get, "ada@example.com", 1)

    await call(code.set, "482913", "ada@example.com", 1)

    assert before is None
    assert await call(code.get, "ada@example.com", 1) == "482913"


async def test_a_value_lives_for_its_ttl(
    side: Side,
    new_process_cache: NewCache,
    clock: Clock,
) -> None:
    code = _login_code(new_process_cache(clock=clock), side)
    await call(code.set, "482913", "ada@example.com", 1)

    clock.now += 601

    assert await call(code.get, "ada@example.com", 1) is None


async def test_a_value_is_dropped_by_invalidate_and_by_its_tags(side: Side, new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    code = _login_code(cache, side)
    await call(code.set, "1", "ada@example.com", 1)
    await call(code.set, "2", "bob@example.com", 2)

    removed = await call(code.invalidate, "ada@example.com", 1)
    await call(cache.invalidate_tags, "user:2")

    assert removed
    assert await call(code.get, "ada@example.com", 1) is None
    assert await call(code.get, "bob@example.com", 2) is None


async def test_a_value_of_a_failing_backend_raises(side: Side) -> None:
    backend = side.failing_memory()
    code = _login_code(side.new_cache(backend), side)
    backend.down = True

    with pytest.raises(BackendError):
        await call(code.get, "ada@example.com", 1)


async def test_get_of_a_cached_function_reads_without_loading(new_process_cache: NewCache) -> None:
    cache, source = new_process_cache(), Source()
    get_user = cached_function(cache, source, ttl=60, key="user:{user_id}")
    missing = await call(get_user.get, 1)
    await call(get_user, 1)

    cached = await call(get_user.get, 1)

    assert missing is None
    assert cached == {"id": 1, "version": 1}
    assert source.calls == 1


# Errors of the loader


async def test_negative_caching_keeps_a_not_found(new_process_cache: NewCache) -> None:
    outcomes: list[Outcome] = []
    cache = new_process_cache(hooks=[RecordingHook(outcomes=outcomes)])
    source = Source()
    source.error = UserNotFoundError()
    get_user = cached_function(cache, source, ttl=60, negative=Negative(on=(UserNotFoundError,), ttl=30))

    with pytest.raises(NotFoundError) as loaded:
        await call(get_user, 1)
    with pytest.raises(NotFoundError) as cached:
        await call(get_user, 1)

    assert isinstance(loaded.value.__cause__, UserNotFoundError)
    assert cached.value.__cause__ is None
    assert source.calls == 1
    assert results(outcomes) == [CacheStatus.MISS, CacheStatus.NOT_FOUND]


async def test_a_not_found_is_asked_again_after_its_ttl(new_process_cache: NewCache, clock: Clock) -> None:
    cache = new_process_cache(clock=clock)
    source = Source()
    source.error = UserNotFoundError()
    get_user = cached_function(cache, source, ttl=60, negative=Negative(on=(UserNotFoundError,), ttl=30))
    with pytest.raises(NotFoundError):
        await call(get_user, 1)
    source.error = None

    clock.now += 31
    user = await call(get_user, 1)

    assert user == {"id": 1, "version": 1}
    assert source.calls == 2


async def test_loader_errors_are_not_cached(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    source.error = RuntimeError("source is down")
    get_user = cached_function(cache, source, ttl=60)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await call(get_user, 1)

    assert source.calls == 2


# Stale results


async def test_stale_while_revalidate_answers_at_once_and_reloads(new_process_cache: NewCache, clock: Clock) -> None:
    outcomes: list[Outcome] = []
    cache = new_process_cache(clock=clock, hooks=[RecordingHook(outcomes=outcomes)])
    source = Source()
    options: dict[str, object] = {"ttl": 60, "stale": Stale(while_revalidate=600)}
    get_user = cached_function(cache, source, **options)
    await call(get_user, 1)
    clock.now += 61
    source.version = 2

    stale = await call(get_user, 1)
    await close(cache)
    later = new_process_cache(clock=clock, hooks=[RecordingHook(outcomes=outcomes)])  # a closed backend takes no calls
    fresh = await call(cached_function(later, source, **options), 1)

    assert stale == {"id": 1, "version": 1}
    assert fresh == {"id": 1, "version": 2}
    assert results(outcomes) == [CacheStatus.MISS, CacheStatus.STALE_WHILE_REVALIDATE, CacheStatus.HIT]


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_a_reload_in_the_background_slower_than_its_window_still_stores(
    new_process_cache: NewCache, clock: Clock
) -> None:
    version = 1

    async def load_version() -> int:
        if version > 1:
            await asyncio.sleep(0.2)  # longer than the window
        return version

    cache = new_process_cache(clock=clock)

    assert isinstance(cache, AsyncCache)
    get_version = cache(ttl=60, stale=Stale(while_revalidate=0.05))(load_version)
    await get_version()
    clock.now += 60.01
    version = 2

    stale = await get_version()
    await cache.aclose()
    later = new_process_cache(clock=clock)  # a closed backend takes no calls
    assert isinstance(later, AsyncCache)
    fresh = await later(ttl=60, stale=Stale(while_revalidate=0.05))(load_version)()

    assert (stale, fresh) == (1, 2)


async def test_stale_if_error_answers_a_failing_loader(new_process_cache: NewCache, clock: Clock) -> None:
    failures: list[Failure] = []
    outcomes: list[Outcome] = []
    cache = new_process_cache(clock=clock, hooks=[RecordingHook(outcomes=outcomes, failures=failures)])
    source = Source()
    get_user = cached_function(cache, source, ttl=60, stale=Stale(if_error=IfError(600, on=(RuntimeError,))))
    await call(get_user, 1)
    clock.now += 61
    source.error = RuntimeError("down")

    user = await call(get_user, 1)

    assert user == {"id": 1, "version": 1}
    assert results(outcomes)[-1] is CacheStatus.STALE_IF_ERROR
    assert isinstance(failures[-1].error, RuntimeError)  # as the loader raised it, for the hooks


async def test_stale_if_error_lets_other_errors_through(new_process_cache: NewCache, clock: Clock) -> None:
    cache = new_process_cache(clock=clock)
    source = Source()
    get_user = cached_function(cache, source, ttl=60, stale=Stale(if_error=IfError(600, on=(RuntimeError,))))
    await call(get_user, 1)
    clock.now += 61
    source.error = ValueError("not a failure it answers")

    with pytest.raises(ValueError, match="not a failure"):
        await call(get_user, 1)


async def test_stale_if_error_takes_a_timedelta(clock: Clock) -> None:
    cache = AsyncCache(AsyncMemoryBackend(), clock=clock)
    source = Source()
    stale = Stale(if_error=timedelta(minutes=1))
    get_user = cached_function(cache, source, ttl=timedelta(seconds=10), stale=stale)
    await get_user(1)
    clock.now += 30
    source.error = RuntimeError("the source is down")

    user = await get_user(1)

    assert user == {"id": 1, "version": 1}  # within the window of Stale.if_error


async def test_stale_if_slow_answers_while_the_load_goes_on(side: Side, clock: Clock) -> None:
    outcomes: list[Outcome] = []
    slow = False
    get_user: CachedFunction[[int], int] | AsyncCachedFunction[[int], int]
    cache: EitherCache
    if side is SYNC:
        cache = sync_cache = Cache(MemoryBackend(), hooks=[RecordingHook(outcomes=outcomes)], clock=clock)

        @sync_cache(ttl=60, stale=Stale(if_slow=IfSlow(600, after=0.05)))
        def load_user(user_id: int) -> int:
            if slow:
                time.sleep(0.3)
            return user_id * 10 + int(slow)

        get_user = load_user
    else:
        cache = async_cache = AsyncCache(AsyncMemoryBackend(), hooks=[RecordingHook(outcomes=outcomes)], clock=clock)

        @async_cache(ttl=60, stale=Stale(if_slow=IfSlow(600, after=0.05)))
        async def aload_user(user_id: int) -> int:
            if slow:
                await asyncio.sleep(0.3)
            return user_id * 10 + int(slow)

        get_user = aload_user
    await call(get_user, 1)
    clock.now += 61
    slow = True

    stale = await call(get_user, 1)
    await close(cache)
    fresh = await call(get_user, 1)

    assert (stale, fresh) == (10, 11)
    assert results(outcomes)[1] is CacheStatus.STALE_IF_SLOW


# Stampedes


async def test_revalidate_before_reloads_a_fresh_result_in_its_last_seconds(
    new_process_cache: NewCache, clock: Clock
) -> None:
    outcomes: list[Outcome] = []
    cache = new_process_cache(clock=clock, hooks=[RecordingHook(outcomes=outcomes)])
    source = Source()
    options: dict[str, object] = {"ttl": 60, "stampede": Stampede(revalidate_before=10)}
    get_user = cached_function(cache, source, **options)
    await call(get_user, 1)
    source.version = 2

    clock.now += 40
    early = await call(get_user, 1)
    clock.now += 15
    due = await call(get_user, 1)
    await close(cache)
    later = new_process_cache(clock=clock, hooks=[RecordingHook(outcomes=outcomes)])  # a closed backend takes no calls
    reloaded = await call(cached_function(later, source, **options), 1)

    assert (early["version"], due["version"], reloaded["version"]) == (1, 1, 2)
    assert source.calls == 2
    assert results(outcomes) == [CacheStatus.MISS, CacheStatus.HIT, CacheStatus.HIT, CacheStatus.HIT]


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_single_flight_shares_one_load_between_tasks(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, AsyncCache)
    started = 0
    release = asyncio.Event()

    @cache(ttl=60, stampede=Stampede(single_flight=True))
    async def get_user(user_id: int) -> int:
        nonlocal started
        started += 1
        await release.wait()
        return user_id

    calls = [asyncio.create_task(get_user(1)) for _ in range(5)]
    await asyncio.sleep(0.01)
    release.set()
    users = await asyncio.gather(*calls)

    assert users == [1] * 5
    assert started == 1


@pytest.mark.parametrize("side", ["sync"], indirect=True)
def test_single_flight_shares_one_load_between_threads(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, Cache)
    started = 0
    release = threading.Event()

    @cache(ttl=60, stampede=Stampede(single_flight=True))
    def get_user(user_id: int) -> int:
        nonlocal started
        started += 1
        release.wait(1)
        return user_id

    users: list[int] = []
    threads = [threading.Thread(target=lambda: users.append(get_user(1))) for _ in range(5)]

    for thread in threads:
        thread.start()
    time.sleep(0.05)
    release.set()
    for thread in threads:
        thread.join()

    assert users == [1] * 5
    assert started == 1


@pytest.mark.parametrize("side", ["sync"], indirect=True)
def test_threads_that_share_a_failing_load_each_get_its_error(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, Cache)
    started = 0
    release = threading.Event()

    @cache(ttl=60)
    def get_user(user_id: int) -> int:
        nonlocal started
        started += 1
        release.wait(1)
        msg = f"user {user_id} is gone"
        raise LookupError(msg)

    errors: list[BaseException] = []

    def fetch() -> None:
        try:
            get_user(1)
        except LookupError as error:
            errors.append(error)

    threads = [threading.Thread(target=fetch) for _ in range(5)]
    for thread in threads:
        thread.start()
    time.sleep(0.05)
    release.set()
    for thread in threads:
        thread.join()

    assert [str(error) for error in errors] == ["user 1 is gone"] * 5
    assert started == 1


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_a_waiter_loads_when_the_caller_it_waited_for_is_cancelled(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, AsyncCache)
    loads = 0
    loading = asyncio.Event()

    @cache(ttl=60)
    async def get_user(user_id: int) -> int:  # noqa: ARG001 - the argument names the key
        nonlocal loads
        loads += 1
        loading.set()
        await asyncio.sleep(0.05)
        return loads

    first = asyncio.create_task(get_user(1))
    await loading.wait()  # it leads the flight, past the read of the store
    waiter = asyncio.create_task(get_user(1))
    await asyncio.sleep(0)  # the waiter joins the flight

    first.cancel()
    loaded = await waiter

    assert loaded == 2
    assert await get_user(1) == 2


async def test_lock_for_loads_once_for_all_processes() -> None:
    backend = AsyncMemoryBackend()
    loads = 0

    def cached(cache: AsyncCache) -> AsyncCachedFunction[[int], int]:
        @cache(ttl=60, key="user:{user_id}", stampede=Stampede(lock_for=5))
        async def get_user(user_id: int) -> int:
            nonlocal loads
            loads += 1
            await asyncio.sleep(0.05)
            return user_id

        return get_user

    first, second = cached(AsyncCache(backend)), cached(AsyncCache(backend))

    users = await asyncio.gather(first(1), second(1))

    assert list(users) == [1, 1]
    assert loads == 1


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_a_call_after_an_invalidation_shares_no_load_started_before_it(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, AsyncCache)
    version = 1
    loading = asyncio.Event()

    @cache(ttl=60, tags=["users"])
    async def get_version() -> int:
        read = version
        loading.set()
        await asyncio.sleep(0.05)
        return read

    before = asyncio.create_task(get_version())
    await loading.wait()  # it read version 1
    version = 2
    await cache.invalidate_tags("users")
    after = await get_version()

    assert (await before, after) == (1, 2)


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_a_load_that_started_before_invalidate_is_neither_shared_nor_stored(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, AsyncCache)
    version = 1
    loading = asyncio.Event()

    @cache(ttl=60, key="user:{user_id}")
    async def get_version(user_id: int) -> int:  # noqa: ARG001 - the key names it
        read = version
        loading.set()
        await asyncio.sleep(0.05)
        return read

    before = asyncio.create_task(get_version(1))
    await loading.wait()  # it read version 1
    version = 2
    await get_version.invalidate(1)
    after = await get_version(1)

    assert (await before, after, await get_version(1)) == (1, 2, 2)


@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_max_concurrent_loads_limits_concurrent_loads(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    assert isinstance(cache, AsyncCache)
    running = peak = 0

    @cache(ttl=60, stampede=Stampede(max_concurrent_loads=1))
    async def get_user(user_id: int) -> int:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return user_id

    users = await asyncio.gather(*(get_user(user_id) for user_id in range(4)))

    assert users == [0, 1, 2, 3]
    assert peak == 1


async def test_a_function_that_calls_itself_loads_within_its_one_slot(side: Side) -> None:
    stampede = Stampede(max_concurrent_loads=1)
    depth: CachedFunction[[int], int] | AsyncCachedFunction[[int], int]
    if side is SYNC:
        sync_cache = Cache(MemoryBackend())

        @sync_cache(ttl=60, stampede=stampede)
        def load_depth(node: int) -> int:
            return 0 if node == 0 else 1 + load_depth(node - 1)

        depth = load_depth
    else:
        async_cache = AsyncCache(AsyncMemoryBackend())

        @async_cache(ttl=60, stampede=stampede)
        async def aload_depth(node: int) -> int:
            return 0 if node == 0 else 1 + await aload_depth(node - 1)

        depth = aload_depth

    found = await asyncio.wait_for(call(depth, 3), timeout=1)

    assert found == 3


@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_jitter_spreads_when_results_expire(new_process_cache: NewCache, clock: Clock) -> None:
    cache = new_process_cache(clock=clock)
    assert isinstance(cache, AsyncCache)
    source = Source()
    get_user = cached_function(cache, source, ttl=100, stampede=Stampede(jitter=0.5))
    for user_id in range(20):
        await get_user(user_id)

    clock.now += 100  # past the TTL without the jitter: some of them are fresh still
    for user_id in range(20):
        await get_user(user_id)

    assert 20 < source.calls < 40


# A failing backend


async def test_the_logging_hook_logs_what_a_failing_backend_worked_around(
    side: Side, caplog: pytest.LogCaptureFixture
) -> None:
    backend = side.failing_memory()
    cache = side.new_cache(backend, hooks=[LoggingHook()])
    get_user = cached_function(cache, Source(), ttl=60, key="user:{user_id}")
    backend.down = True

    with caplog.at_level(logging.WARNING, logger="pashe"):
        await call(get_user, 1)

    (record,) = caplog.records
    assert record.message == "pashe: get 'user:1': the backend is down"
    assert (record.pashe_operation, record.pashe_key) == ("get", "user:1")  # type: ignore[attr-defined]  # extra
    assert record.exc_info is not None


async def test_a_failing_backend_loads_and_reports(side: Side) -> None:
    failures: list[Failure] = []
    backend = side.failing_memory()
    cache = side.new_cache(backend, hooks=[RecordingHook(failures=failures)])
    source = Source()
    get_user = cached_function(cache, source, ttl=60, key="user:{user_id}")
    backend.down = True

    users = [await call(get_user, 1), await call(get_user, 1)]

    assert users == [{"id": 1, "version": 1}] * 2
    assert source.calls == 2
    assert all(isinstance(failure.error, BackendError) for failure in failures)
    assert (failures[0].operation, failures[0].key) == (Operation.GET, "user:1")


async def test_the_fallback_answers_while_the_backend_fails(side: Side) -> None:
    outcomes: list[Outcome] = []
    backend = side.failing_memory()
    cache = side.new_cache(backend, hooks=[RecordingHook(outcomes=outcomes)], fallback=Fallback(side.memory()))
    source = Source()
    get_user = cached_function(cache, source, ttl=60)
    backend.down = True

    await call(get_user, 1)
    user = await call(get_user, 1)

    assert user == {"id": 1, "version": 1}
    assert source.calls == 1
    assert results(outcomes) == [CacheStatus.MISS, CacheStatus.FALLBACK]


@pytest.mark.parametrize(("elapsed", "loads"), [(9, 1), (11, 2)])
async def test_a_result_stays_in_the_fallback_for_its_ttl(
    side: Side,
    clock: Clock,
    elapsed: float,
    loads: int,
) -> None:
    backend = side.failing_memory()
    kept = side.memory(clock=clock)
    cache = side.new_cache(backend, clock=clock, fallback=Fallback(kept, ttl=10))
    source = Source()
    get_user = cached_function(cache, source, ttl=60)
    backend.down = True
    await call(get_user, 1)

    clock.now += elapsed
    await call(get_user, 1)

    assert source.calls == loads


class _WritesFail(FailingMemoryBackend):
    """Reads work until down is set; writes fail while writes_broken is."""

    def __init__(self) -> None:
        super().__init__()

        self.writes_broken = False

    @override
    def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        if self.writes_broken:
            msg = "the backend refuses writes"
            raise BackendError(msg)
        super().set(key, value, ttl=ttl)

    @override
    def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        if self.writes_broken:
            msg = "the backend refuses writes"
            raise BackendError(msg)
        super().set_many(values, ttl=ttl)


def test_the_fallback_answers_a_tagged_result_whose_write_failed() -> None:
    outcomes: list[Outcome] = []
    backend = _WritesFail()
    cache = Cache(backend, hooks=[RecordingHook(outcomes=outcomes)], fallback=Fallback(MemoryBackend()))
    source = Source()
    get_user = cached_function(cache, source, ttl=60, tags=["users"])
    get_user(1)  # the tag is known to the backend from now on
    get_user.invalidate(1)
    backend.writes_broken = True

    get_user(1)  # loads, and keeps the result in the fallback
    backend.down = True
    user = get_user(1)

    assert user == {"id": 1, "version": 1}
    assert source.calls == 2
    assert results(outcomes)[-1] is CacheStatus.FALLBACK


# What is stored, and how


async def test_store_when_skips_the_results_it_refuses(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    source = Source()
    get_user = cached_function(cache, source, ttl=60, store=Store(when=lambda user: user["version"] > 1))

    await call(get_user, 1)
    await call(get_user, 1)

    assert source.calls == 2


@dataclass
class User:
    id: int
    name: str


async def test_typed_results_read_back_as_their_type() -> None:
    cache = AsyncCache(AsyncMemoryBackend(), codec=MsgspecJsonCodec())

    @cache(ttl=60)
    async def get_user(user_id: int) -> User:
        return User(user_id, "Ann")

    await get_user(1)
    user = await get_user(1)

    assert user == User(1, "Ann")


@dataclass
class _Before:
    name: str


@dataclass
class _After:
    name: str
    email: str = ""  # old entries decode as this type too: only the shape makes them misses


async def test_a_changed_value_type_makes_old_entries_misses(side: Side) -> None:
    backend = side.memory()
    loads: list[str] = []

    def before() -> _Before:
        loads.append("before")
        return _Before("ann")

    def after() -> _After:
        loads.append("after")
        return _After("ann", "ann@example.com")

    deploys = [side.function(before), side.function(after), side.function(after)]

    for function in deploys:
        cache = side.new_cache(backend, codec=MsgspecJsonCodec())
        await call(cache(ttl=60, key="user")(function))
        await close(cache)

    assert loads == ["before", "after"]  # the old entry did not decode as the new type


async def test_a_function_without_a_return_annotation_is_cached(side: Side, new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    calls = 0

    def get_user(user_id):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN202 - what the test is about
        nonlocal calls
        calls += 1
        return {"id": user_id}

    cached = cache(ttl=60)(side.function(get_user))

    users = [await call(cached, 1), await call(cached, 1)]

    assert users == [{"id": 1}] * 2  # decoded as the codec reads it back on its own
    assert calls == 1


async def test_a_compressor_shrinks_what_is_stored() -> None:
    backend = AsyncMemoryBackend()
    cache = AsyncCache(backend, compressor=GzipCompressor())

    @cache(ttl=60, key="text")
    async def text() -> str:
        return "pashe " * 1000

    loaded = await text()
    cached = await text()

    stored = await backend.get("text")
    assert loaded == cached == "pashe " * 1000
    assert stored is not None
    assert len(stored) < 1000


async def test_tags_and_rate_limits_work_with_a_compressor() -> None:
    cache = AsyncCache(AsyncMemoryBackend(), compressor=GzipCompressor())
    loads = 0

    @cache(ttl=60, tags=["answers"])
    async def answer() -> int:
        nonlocal loads
        loads += 1
        return 42

    await answer()
    await cache.invalidate_tags("answers")
    await answer()
    state = await cache.rate_limit("api", per_second(5))

    assert loads == 2
    assert state is not None
    assert state.remaining == 4


# Keys


async def test_methods_are_cached_without_self_in_the_key() -> None:
    cache = AsyncCache(AsyncMemoryBackend())
    loads = 0

    class Users:
        @cache(ttl=60)
        async def get(self, user_id: int) -> int:
            nonlocal loads
            loads += 1
            return user_id

    await Users().get(1)
    await Users().get(1)

    assert loads == 1
    assert await Users().get.invalidate(1)


async def test_a_parameter_named_cls_is_a_part_of_the_key() -> None:
    cache = AsyncCache(AsyncMemoryBackend())

    @cache(ttl=60)
    async def by_class(cls: str) -> str:
        return cls

    answers = [await by_class("a"), await by_class("b")]

    assert answers == ["a", "b"]


class Color(enum.Enum):
    RED = 1


async def test_an_enum_and_its_value_have_keys_of_their_own() -> None:
    cache = AsyncCache(AsyncMemoryBackend())

    @cache(ttl=60)
    async def describe(color: Color | int) -> str:
        return str(color)

    answers = [await describe(Color.RED), await describe(1)]

    assert answers == ["Color.RED", "1"]


async def test_the_default_key_refuses_arguments_without_a_stable_repr() -> None:
    cache = AsyncCache(AsyncMemoryBackend())

    @cache(ttl=60)
    async def count(items: object) -> int:
        return len(str(items))

    with pytest.raises(TypeError, match="key="):
        await count(object())


# Batches


async def test_no_cache_loads_and_stores_what_it_loaded_for_the_calls_after_it(new_process_cache: NewCache) -> None:
    cache, source = new_process_cache(), Source()
    get_user = cached_function(cache, source, ttl=60)
    await call(get_user, 1)
    source.version = 2

    with pashe.no_cache():
        reloaded = await call(get_user, 1)
    after = await call(get_user, 1)

    assert reloaded == after == {"id": 1, "version": 2}
    assert source.calls == 2  # the call after the block is answered from what the block stored


async def test_get_finds_nothing_in_no_cache(new_process_cache: NewCache) -> None:
    cache, source = new_process_cache(), Source()
    get_user = cached_function(cache, source, ttl=60)
    await call(get_user, 1)

    with pashe.no_cache():
        found = await call(get_user.get, 1)

    assert found is None


async def test_a_batch_loads_every_item_in_no_cache(new_process_cache: NewCache) -> None:
    asked: list[list[int]] = []
    get_items = batch_function(new_process_cache(), asked)
    await call(get_items, [1, 2])

    with pashe.no_cache():
        await call(get_items, [1, 2])
    await call(get_items, [1, 2])

    assert asked == [[1, 2], [1, 2]]


async def test_a_batch_loads_only_the_missing_items(new_process_cache: NewCache) -> None:
    asked: list[list[int]] = []
    get_items = batch_function(new_process_cache(), asked, left_out=frozenset({3}))
    await call(get_items, [1, 2])

    items = await call(get_items, [1, 2, 3])

    assert items == {1: 10, 2: 20}
    assert asked == [[1, 2], [3]]


async def test_a_batch_answers_from_the_fallback_while_the_backend_fails(side: Side) -> None:
    backend = side.failing_memory()
    asked: list[list[int]] = []
    get_items = batch_function(side.new_cache(backend, fallback=Fallback(side.memory())), asked)
    backend.down = True
    await call(get_items, [1, 2])

    items = await call(get_items, [1, 2, 3])

    assert items == {1: 10, 2: 20, 3: 30}
    assert asked == [[1, 2], [3]]


async def test_a_batch_loads_and_reports_while_the_backend_fails(side: Side) -> None:
    failures: list[Failure] = []
    backend = side.failing_memory()
    asked: list[list[int]] = []
    get_items = batch_function(side.new_cache(backend, hooks=[RecordingHook(failures=failures)]), asked)
    backend.down = True

    items = [await call(get_items, [1]), await call(get_items, [1])]

    assert items == [{1: 10}] * 2
    assert asked == [[1], [1]]
    assert failures
    assert all(isinstance(failure.error, BackendError) for failure in failures)


def test_a_batch_keeps_in_the_fallback_what_it_could_not_write() -> None:
    backend = _WritesFail()
    asked: list[list[int]] = []
    get_items = batch_function(Cache(backend, fallback=Fallback(MemoryBackend())), asked)
    backend.writes_broken = True

    get_items([1])
    backend.down = True
    items = get_items([1])

    assert items == {1: 10}
    assert asked == [[1]]


def test_batch_items_must_be_hashable() -> None:
    def by_lists(items: list[list[int]]) -> dict[list[int], int]:  # noqa: ARG001 - the signature of a batch function
        return {}

    # mypy refuses items a dict cannot hold as keys; strict mypy fails here if it stops refusing them
    Cache(MemoryBackend()).batch(ttl=60)(by_lists)  # type: ignore[type-var]


def test_a_batch_that_does_not_return_a_dict_is_refused_at_the_decorator() -> None:
    def by_ids(ids: list[int]) -> list[int]:
        return ids

    with pytest.raises(InvalidOptionsError, match=r"by_ids must return dict\[K, V\], not list\[int\]"):
        Cache(MemoryBackend()).batch(ttl=60)(by_ids)  # type: ignore[arg-type]  # the misfit it tests


# Options


@dataclass
class _Plan:
    id: int


@pytest.mark.parametrize("codec", json_codecs(), ids=lambda codec: type(codec).__name__)
def test_a_return_type_json_reads_back_as_another_is_refused_at_the_decorator(
    side: Side,
    new_process_cache: NewCache,
    codec: Codec,
) -> None:
    cache = new_process_cache(codec=codec, compressor=GzipCompressor())  # the compressor passes the check on

    def get_plan(plan_id: int) -> _Plan:
        return _Plan(plan_id)

    with pytest.raises(InvalidOptionsError, match="reads _Plan back as another type"):
        cache(ttl=60)(side.function(get_plan))


class _Deploy:
    """A deploy."""

    type Result = list[int]


class _NextDeploy:
    """The next deploy: Result is of the same name, for another type."""

    type Result = dict[str, int]


def test_a_type_alias_whose_value_changed_makes_its_stored_results_a_miss() -> None:
    backend = MemoryBackend()

    def get_before(result_id: int) -> object:
        return [result_id]

    def get_after(result_id: int) -> object:
        return {"id": result_id}

    get_before.__annotations__["return"] = _Deploy.Result
    get_after.__annotations__["return"] = _NextDeploy.Result
    Cache(backend)(ttl=60, key="result:{result_id}")(get_before)(1)

    found = Cache(backend)(ttl=60, key="result:{result_id}")(get_after)(1)

    assert found == {"id": 1}


def test_a_lambda_without_a_key_is_refused_at_the_decorator() -> None:
    cache = Cache(MemoryBackend())

    with pytest.raises(InvalidOptionsError, match="lambda"):
        cache(ttl=60)(lambda user_id: user_id)


def test_a_return_type_not_defined_yet_is_refused_at_the_decorator(side: Side, new_process_cache: NewCache) -> None:
    cache = new_process_cache()

    def get_plan(plan_id: int) -> _Later:  # type: ignore[name-defined]  # noqa: F821 - the name it tests
        return _Plan(plan_id)

    with pytest.raises(InvalidOptionsError, match="annotated with _Later, which is not defined yet"):
        cache(ttl=60)(side.function(get_plan))


async def test_a_codec_that_rebuilds_the_type_takes_it(side: Side, new_process_cache: NewCache) -> None:
    cache = new_process_cache(codec=MsgspecJsonCodec())

    def get_plan(plan_id: int) -> _Plan:
        return _Plan(plan_id)

    cached = cache(ttl=60)(side.function(get_plan))
    await call(cached, 1)

    plan = await call(cached, 1)

    assert plan == _Plan(1)


class _Growing(Compressor):
    """A compressor whose output is longer than what it was given, as gzip makes of a short value."""

    @property
    @override
    def min_size(self) -> int:
        return 0

    @override
    def compress(self, data: bytes, /) -> bytes:
        return data + b"padding"

    @override
    def decompress(self, data: bytes, /) -> bytes:
        return data.removesuffix(b"padding")


@pytest.mark.parametrize(
    ("compressor", "value", "compressed"),
    [
        (GzipCompressor(min_size=100), "a", False),
        (GzipCompressor(min_size=100), "a" * 1000, True),
        (_Growing(), "a" * 1000, False),
    ],
    ids=["shorter than min_size", "from min_size", "one compression would grow"],
)
def test_a_value_is_compressed_from_min_size_and_only_if_it_shrinks(
    compressor: Compressor,
    value: str,
    *,
    compressed: bool,
) -> None:
    backend = MemoryBackend()
    cache = Cache(backend, compressor=compressor)

    @cache(ttl=60, key="k")
    def load() -> str:
        return value

    load()

    raw = backend.get("k")
    assert raw is not None
    assert raw.endswith(f'"{value}"'.encode()) is not compressed
    assert load() == value


def test_an_entry_of_the_format_before_is_a_miss() -> None:
    backend, source = MemoryBackend(), Source()
    cache = Cache(backend)
    get_user = cached_function(cache, source, ttl=60, key="user")
    backend.set("user", b"\x02" + b"\x00" * 19 + b'{"id": 1}')  # as pashe wrote it before the payload had a flag

    get_user(1)

    assert source.calls == 1


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: Cache(MemoryBackend())(ttl=-1), "ttl is -1"),
        (lambda: Cache(MemoryBackend())(ttl=0), "no result would ever be stored"),
        (lambda: IfSlow(600, after=0), r"IfSlow\.after is 0"),
        (lambda: IfError(-1), r"IfError\.window is -1"),
        (lambda: Stampede(revalidate_before=-1), r"Stampede\.revalidate_before is -1"),
        (lambda: Cache(MemoryBackend())(ttl=10, stampede=Stampede(revalidate_before=10)), "must be shorter"),
        (
            lambda: Cache(MemoryBackend())(ttl=60, stampede=Stampede(revalidate_before=40, jitter=0.5)),
            "jitter counted",
        ),
        (lambda: Stampede(jitter=1.5), r"Stampede\.jitter is 1\.5"),
        (lambda: Stampede(max_concurrent_loads=-1), r"Stampede\.max_concurrent_loads is -1"),
        (lambda: Negative(ttl=30), r"Negative\.on is empty"),
        (lambda: Negative(on=(ValueError,)), r"Negative\.ttl is 0"),
        (lambda: Store(slower_than=-1), r"Store\.slower_than is -1"),
        (lambda: Fallback(MemoryBackend(), ttl=0), r"Fallback\.ttl is 0"),
        (lambda: Cache(MemoryBackend()).batch(ttl=60, stampede=Stampede(lock_for=5)), "lock_for"),
        (
            lambda: Cache(MemoryBackend()).batch(ttl=60, stampede=Stampede(revalidate_before=5)),
            "revalidate_before",
        ),
    ],
)
def test_options_that_cannot_work_together_are_refused(make: Callable[[], object], message: str) -> None:
    with pytest.raises(InvalidOptionsError, match=message):
        make()


def _as_untyped(value: object) -> Any:
    return value


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: Cache(MemoryBackend(), prefix=_as_untyped(1)), "prefix must be str, not int"),
        (
            lambda: Cache(MemoryBackend(), hooks=_as_untyped(print)),
            "hooks must be list or tuple, not builtin_function_or_method",
        ),
        (
            lambda: Cache(MemoryBackend())(ttl=_as_untyped("60")),
            "ttl must be int or float or timedelta or a function, not str",
        ),
        (lambda: Cache(MemoryBackend())(ttl=60, tags=_as_untyped("users")), "tags must be list or tuple, not str"),
        (lambda: Cache(MemoryBackend())(ttl=60, tags=_as_untyped(["users", 1])), r"tags\[1\] must be str, not int"),
        (lambda: Cache(MemoryBackend())(ttl=60, stale=_as_untyped({"if_error": 60})), "stale must be Stale, not dict"),
        (
            lambda: Stale(if_error=_as_untyped("60")),
            "Stale.if_error must be int or float or timedelta or IfError, not str",
        ),
        (lambda: Stampede(single_flight=_as_untyped(1)), "Stampede.single_flight must be bool, not int"),
        (lambda: Negative(on=_as_untyped((ValueError, 1)), ttl=30), r"Negative.on\[1\] must be a class of exceptions"),
        (lambda: Negative(on=_as_untyped([ValueError]), ttl=30), "Negative.on must be tuple, not list"),
        (lambda: Store(when=_as_untyped("active")), "Store.when must be a function or None, not str"),
        (lambda: Cache(MemoryBackend(), hooks=[_as_untyped(print)]), r"hooks\[0\] must be Hook, not builtin"),
        (
            lambda: Cache(MemoryBackend(), fallback=_as_untyped(MemoryBackend())),
            "fallback must be Fallback or None",
        ),
        (
            lambda: Cache(MemoryBackend(), fallback=_as_untyped(Fallback(AsyncMemoryBackend()))),
            "Fallback.backend must be Backend, not AsyncMemoryBackend",
        ),
    ],
)
def test_options_are_checked_against_their_types(make: Callable[[], object], message: str) -> None:
    with pytest.raises(TypeError, match=message):
        make()


def test_a_function_of_the_other_side_is_refused() -> None:
    def get_user(user_id: int) -> int:
        return user_id

    async def aget_user(user_id: int) -> int:
        return user_id

    with pytest.raises(TypeError, match="AsyncCache"):
        Cache(MemoryBackend())(ttl=60)(aget_user)  # mypy cannot tell: a coroutine function is a callable
    with pytest.raises(TypeError, match="Cache"):
        AsyncCache(AsyncMemoryBackend())(ttl=60)(get_user)  # type: ignore[arg-type]


def test_a_function_without_a_name_is_refused() -> None:
    def add(first: int, second: int) -> int:
        return first + second

    with pytest.raises(TypeError, match="no name"):
        Cache(MemoryBackend())(ttl=60)(functools.partial(add, 1))
