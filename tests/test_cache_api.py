"""The basic API, locks and rate limits of a cache, on both sides."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, override

import pytest

import pashe
from pashe import AsyncCache, Cache
from pashe.backends import AsyncMemoryBackend, MemoryBackend, NearCacheBackend
from pashe.errors import BackendError, InvalidOptionsError, LockLostError, LockTimeoutError, RateLimitedError
from pashe.options import Fallback
from pashe.ratelimit import FixedWindow, SlidingWindow, per_second
from tests.harness.helpers import RecordingHook, call

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.harness.helpers import Clock, NewCache


class _ExtensionsFail(MemoryBackend):
    """A backend that cannot extend a lock while down is set, as one unreachable for longer than its ttl."""

    def __init__(self) -> None:
        super().__init__()

        self.down = False

    @override
    def expire_if_equals(self, key: str, value: bytes, ttl: float, /) -> bool:
        if self.down:
            msg = "the backend is down"
            raise BackendError(msg)
        return super().expire_if_equals(key, value, ttl)


class _AsyncExtensionsFail(AsyncMemoryBackend):
    """The async side of _ExtensionsFail."""

    def __init__(self) -> None:
        super().__init__()

        self.down = False

    @override
    async def expire_if_equals(self, key: str, value: bytes, ttl: float, /) -> bool:
        if self.down:
            msg = "the backend is down"
            raise BackendError(msg)
        return await super().expire_if_equals(key, value, ttl)


class _Closing(MemoryBackend):
    def __init__(self) -> None:
        super().__init__()

        self.closed = False

    @override
    def close(self) -> None:
        self.closed = True


def test_version() -> None:
    assert pashe.__version__


async def test_ping(new_process_cache: NewCache) -> None:
    cache = new_process_cache()

    await call(cache.ping)


def test_a_cache_closes_what_it_was_given() -> None:
    backend, fallback = _Closing(), _Closing()

    with Cache(backend, fallback=Fallback(fallback)):
        pass

    assert backend.closed
    assert fallback.closed


# Locks


async def test_try_lock_takes_a_free_lock(new_process_cache: NewCache) -> None:
    cache = new_process_cache()

    lock = await call(cache.try_lock, "job", ttl=10)

    assert lock is not None


async def test_try_lock_of_a_held_lock_answers_none(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    await call(cache.try_lock, "job", ttl=10)

    lock = await call(cache.try_lock, "job", ttl=10)

    assert lock is None


async def test_the_block_of_a_lock_releases_it(side: str, new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    lock = await call(cache.try_lock, "job", ttl=10)
    assert lock is not None

    if side == "sync":
        with lock:
            pass
    else:
        async with lock:
            pass

    assert await call(cache.try_lock, "job", ttl=10) is not None


@pytest.mark.parametrize("side", ["sync"])
def test_a_lock_is_held_while_its_block_runs(new_process_cache: NewCache) -> None:
    cache: Cache = new_process_cache()

    with cache.lock("job", ttl=1) as lease:
        held = cache.try_lock("job", ttl=1)

    assert lease.key == "job"
    assert held is None
    assert cache.try_lock("job", ttl=1) is not None


@pytest.mark.no_leaks(threads=False)
@pytest.mark.parametrize("side", ["async"])
async def test_async_locks_of_one_key_run_one_at_a_time(new_process_cache: NewCache) -> None:
    cache: AsyncCache = new_process_cache()
    order: list[str] = []

    async def worker(name: str) -> None:
        async with cache.lock("job", ttl=1):
            order.append(name)
            await asyncio.sleep(0.02)
            order.append(name)

    await asyncio.gather(worker("a"), worker("b"))

    assert order in (["a", "a", "b", "b"], ["b", "b", "a", "a"])


@pytest.mark.no_leaks(threads=False)
@pytest.mark.parametrize("side", ["async"])
async def test_a_task_cancelled_as_its_lock_block_ends_still_releases_the_lock(new_process_cache: NewCache) -> None:
    cache: AsyncCache = new_process_cache()

    async def worker() -> None:
        async with cache.lock("job", ttl=30):
            asyncio.get_running_loop().call_soon(task.cancel)  # lands while the exit waits for the extender

    task = asyncio.create_task(worker())
    with pytest.raises(asyncio.CancelledError):
        await task

    assert await cache.try_lock("job", ttl=30) is not None


async def test_a_lock_entered_inside_its_own_block_is_refused(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    lock = cache.lock("job", ttl=30)

    if isinstance(cache, Cache):
        with lock:
            with pytest.raises(RuntimeError, match="inside its own block"):
                lock.__enter__()
            held = cache.try_lock("job", ttl=30) is None
    else:
        async with lock:
            with pytest.raises(RuntimeError, match="inside its own block"):
                await lock.__aenter__()
            held = await cache.try_lock("job", ttl=30) is None

    assert held


async def test_a_lock_that_stays_busy_raises_after_its_timeout(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    await call(cache.try_lock, "job", ttl=5)
    lock = cache.lock("job", ttl=5, timeout=0.05)
    enter = lock.__enter__ if isinstance(cache, Cache) else lock.__aenter__

    with pytest.raises(LockTimeoutError):
        await call(enter)


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda cache: cache.lock("job", ttl=0), "ttl is 0"),
        (lambda cache: cache.lock("job", ttl=30, timeout=-1), "timeout is -1"),
        (lambda cache: cache.locked(ttl=30, timeout=-1), "timeout is -1"),
    ],
    ids=["ttl", "timeout", "locked"],
)
def test_lock_options_that_cannot_work_are_refused_before_the_lock_is_taken(
    make: Callable[[Cache], object], message: str
) -> None:
    cache = Cache(MemoryBackend())

    with pytest.raises(InvalidOptionsError, match=message):
        make(cache)


def test_a_lock_lost_is_raised_after_the_block() -> None:
    backend = _ExtensionsFail()
    lock = Cache(backend).lock("job", ttl=0.06)
    lock.__enter__()

    backend.down = True
    time.sleep(0.1)  # an extension is due and fails

    with pytest.raises(LockLostError):
        lock.__exit__(None, None, None)


async def test_an_async_lock_lost_cancels_the_block() -> None:
    backend = _AsyncExtensionsFail()
    cache = AsyncCache(backend)
    finished = False

    async def hold() -> None:
        nonlocal finished
        async with cache.lock("job", ttl=0.06):
            backend.down = True
            await asyncio.sleep(1)
            finished = True

    with pytest.raises(LockLostError):
        await hold()

    assert not finished


def test_a_lock_entered_again_is_extended_again() -> None:
    cache = Cache(MemoryBackend())
    lock = cache.lock("job", ttl=0.15)
    with lock:
        pass

    with lock:
        time.sleep(0.3)  # twice the ttl: only extensions keep it
        held = cache.try_lock("job", ttl=1)

    assert held is None


async def test_an_async_lock_entered_again_is_still_cancelled_when_lost() -> None:
    backend = _AsyncExtensionsFail()
    lock = AsyncCache(backend).lock("job", ttl=0.06)
    async with lock:
        pass

    async def hold() -> None:
        async with lock:
            backend.down = True
            await asyncio.sleep(1)

    with pytest.raises(LockLostError):
        await hold()


def test_a_lock_keeps_apart_from_a_cached_function_of_the_same_key() -> None:
    cache = Cache(MemoryBackend())
    loads = 0

    @cache.locked(ttl=30, timeout=0.2)  # the default keys of both are the name of the function
    @cache(ttl=60)
    def report() -> int:
        nonlocal loads
        loads += 1
        return loads

    reports = [report(), report(), report()]

    assert reports == [1, 1, 1]


# Rate limits


async def test_a_fixed_window_refuses_calls_over_it_for_its_ban(new_process_cache: NewCache) -> None:
    cache = new_process_cache()
    limit = FixedWindow(calls=2, per=60, ban_for=120)
    await call(cache.rate_limit, "api", limit)
    await call(cache.rate_limit, "api", limit)

    with pytest.raises(RateLimitedError) as refused:
        await call(cache.rate_limit, "api", limit)

    assert refused.value.retry_after == 120


async def test_a_sliding_window_refuses_calls_over_it(new_process_cache: NewCache, clock: Clock) -> None:
    clock.now = 1000.0  # the start of a window of one second
    cache = new_process_cache(clock=clock)
    for _ in range(3):
        await call(cache.rate_limit, "api", per_second(3))

    with pytest.raises(RateLimitedError) as refused:
        await call(cache.rate_limit, "api", per_second(3))

    assert 0 < refused.value.retry_after <= 2


async def test_a_sliding_window_lets_calls_through_once_it_passed(new_process_cache: NewCache, clock: Clock) -> None:
    clock.now = 1000.0  # the start of a window of one second
    cache = new_process_cache(clock=clock)
    for _ in range(3):
        await call(cache.rate_limit, "api", per_second(3))

    clock.now += 2  # both windows are past
    state = await call(cache.rate_limit, "api", per_second(3))

    assert state.remaining == 2


async def test_limits_on_one_key_count_apart(new_process_cache: NewCache, clock: Clock) -> None:
    clock.now = 1_000_000.0  # at the start of a window, so the last one does not weigh
    cache = new_process_cache(clock=clock)
    for _ in range(3):
        await call(cache.rate_limit, "ip:1", SlidingWindow(calls=100, per=60))
        await call(cache.rate_limit, "user:1", FixedWindow(calls=100, per=60))

    sliding = await call(cache.rate_limit, "ip:1", SlidingWindow(calls=5, per=60))
    fixed = await call(cache.rate_limit, "user:1", FixedWindow(calls=3, per=3600))

    assert (sliding.remaining, fixed.remaining) == (4, 2)


async def test_the_state_of_a_sliding_window(new_process_cache: NewCache, clock: Clock) -> None:
    clock.now = 1_000_000.0  # at the start of a window, so the last one does not weigh
    cache = new_process_cache(clock=clock)

    first = await call(cache.rate_limit, "api", per_second(3))
    second = await call(cache.rate_limit, "api", per_second(3), cost=2)

    assert (first.limit, first.remaining) == (3, 2)
    assert second.remaining == 0
    assert 0 < second.reset_after <= 1


async def test_the_state_of_a_fixed_window(new_process_cache: NewCache) -> None:
    cache = new_process_cache()

    state = await call(cache.rate_limit, "login", FixedWindow(calls=5, per=60), cost=3)

    assert state.remaining == 2
    assert 59 < state.reset_after <= 60


async def test_a_cost_over_the_limit_is_refused(new_process_cache: NewCache) -> None:
    cache = new_process_cache()

    with pytest.raises(InvalidOptionsError):
        await call(cache.rate_limit, "api", per_second(3), cost=4)


def test_a_hook_of_on_call_and_on_error_alone_hears_rate_limits_and_near_reads() -> None:
    hook = RecordingHook()  # leaves on_rate_limit, on_near_read and on_near_flush as Hook has them
    cache = Cache(NearCacheBackend(MemoryBackend(), MemoryBackend(), hooks=[hook]), hooks=[hook])

    state = cache.rate_limit("ip", FixedWindow(calls=2, per=60, ban_for=60))

    assert state is not None
    assert state.remaining == 1
    assert hook.failures == []
