"""The basic API, locks and rate limits of a cache, on both sides."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, override

import pytest

import pashe
from pashe import AsyncLocks, Cache, Locks, RateLimiter
from pashe.backends import AsyncMemoryBackend, MemoryBackend, NearCacheBackend
from pashe.errors import BackendError, InvalidOptionsError, LockLostError, LockTimeoutError, RateLimitedError
from pashe.hooks import Operation
from pashe.locks import Lock
from pashe.options import Fallback
from pashe.ratelimit import FixedWindow, SlidingWindow
from tests.harness.helpers import LOOP_BLOCK_SECONDS, RecordingHook, call, run_block

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.harness.helpers import Clock, NewCache, NewLimiter, NewLocks, Side


class _ExtensionsFail(MemoryBackend):
    """A backend that cannot extend a lock while down is set, as one unreachable for longer than its ttl."""

    def __init__(self) -> None:
        super().__init__()

        self.down = False

    @override
    def expire_if_equals(
        self,
        key: str,
        value: bytes,
        ttl: float,
        /,
    ) -> bool:
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
    async def expire_if_equals(
        self,
        key: str,
        value: bytes,
        ttl: float,
        /,
    ) -> bool:
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


# What the objects show


def test_a_cache_shows_its_backend_and_prefix(side: Side) -> None:
    cache = side.new_cache(prefix="app:")

    shown = repr(cache)

    assert shown == f"{type(cache).__name__}({side.memory.__name__}(entries=0, max_entries=1000), prefix='app:')"


def test_a_cached_function_shows_its_function(side: Side) -> None:
    def get_user(user_id: int) -> int:
        return user_id

    get_user_cached = side.new_cache()(ttl=60)(side.function(get_user))

    shown = repr(get_user_cached)

    assert shown == f"{type(get_user_cached).__name__}({get_user.__qualname__})"


def test_a_cached_batch_function_shows_its_function(side: Side) -> None:
    def get_users(user_ids: list[int]) -> dict[int, int]:
        return {user_id: user_id for user_id in user_ids}

    get_users_cached = side.new_cache().batch(ttl=60)(side.function(get_users))

    shown = repr(get_users_cached)

    assert shown == f"{type(get_users_cached).__name__}({get_users.__qualname__})"


def test_a_lock_shows_its_key_and_options(side: Side) -> None:
    lock = side.new_locks().lock("report", ttl=30, holders=2)

    shown = repr(lock)

    assert shown == f"{type(lock).__name__}('report', ttl=30.0, timeout=None, holders=2)"


# Locks


async def test_try_lock_takes_a_free_lock(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()

    lock = await call(locks.try_lock, "job", ttl=10)

    assert lock is not None


async def test_try_lock_of_a_held_lock_answers_none(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    await call(locks.try_lock, "job", ttl=10)

    lock = await call(locks.try_lock, "job", ttl=10)

    assert lock is None


async def test_the_block_of_a_lock_releases_it(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    lock = await call(locks.try_lock, "job", ttl=10)
    assert lock is not None

    await run_block(lock)

    assert await call(locks.try_lock, "job", ttl=10) is not None


@pytest.mark.parametrize("side", ["sync"], indirect=True)
def test_a_lock_is_held_while_its_block_runs(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    assert isinstance(locks, Locks)

    with locks.lock("job", ttl=1) as lease:
        held = locks.try_lock("job", ttl=1)

    assert lease.key == "job"
    assert held is None
    assert locks.try_lock("job", ttl=1) is not None


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_async_locks_of_one_key_run_one_at_a_time(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    assert isinstance(locks, AsyncLocks)
    order: list[str] = []

    async def worker(name: str) -> None:
        async with locks.lock("job", ttl=1):
            order.append(name)
            await asyncio.sleep(0.02)
            order.append(name)

    await asyncio.gather(worker("a"), worker("b"))

    assert order in (["a", "a", "b", "b"], ["b", "b", "a", "a"])


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_a_task_cancelled_as_its_lock_block_ends_still_releases_the_lock(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    assert isinstance(locks, AsyncLocks)

    async def worker() -> None:
        async with locks.lock("job", ttl=30):
            asyncio.get_running_loop().call_soon(task.cancel)  # lands while the exit waits for the extender

    task = asyncio.create_task(worker())
    with pytest.raises(asyncio.CancelledError):
        await task

    assert await locks.try_lock("job", ttl=30) is not None


async def test_a_lock_entered_inside_its_own_block_is_refused(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()

    if isinstance(locks, Locks):
        lock = locks.lock("job", ttl=30)
        with lock:
            with pytest.raises(RuntimeError, match="inside its own block"):
                lock.__enter__()
            held = locks.try_lock("job", ttl=30) is None
    else:
        async_lock = locks.lock("job", ttl=30)
        async with async_lock:
            with pytest.raises(RuntimeError, match="inside its own block"):
                await async_lock.__aenter__()
            held = await locks.try_lock("job", ttl=30) is None

    assert held


async def test_a_lock_that_stays_busy_raises_after_its_timeout(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    await call(locks.try_lock, "job", ttl=5)
    lock = locks.lock("job", ttl=5, timeout=0.05)
    enter = lock.__enter__ if isinstance(lock, Lock) else lock.__aenter__

    with pytest.raises(LockTimeoutError):
        await call(enter)


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda locks: locks.lock("job", ttl=0), "ttl is 0"),
        (lambda locks: locks.lock("job", ttl=30, timeout=-1), "timeout is -1"),
        (lambda locks: locks.locked(ttl=30, timeout=-1), "timeout is -1"),
    ],
    ids=["ttl", "timeout", "locked"],
)
def test_lock_options_that_cannot_work_are_refused_before_the_lock_is_taken(
    make: Callable[[Locks], object], message: str
) -> None:
    locks = Locks(MemoryBackend())

    with pytest.raises(InvalidOptionsError, match=message):
        make(locks)


def test_a_lock_lost_is_raised_after_the_block() -> None:
    backend = _ExtensionsFail()
    lock = Locks(backend).lock("job", ttl=0.06)
    lock.__enter__()

    backend.down = True
    time.sleep(0.1)  # an extension is due and fails

    with pytest.raises(LockLostError):
        lock.__exit__(None, None, None)


async def test_an_async_lock_lost_cancels_the_block() -> None:
    backend = _AsyncExtensionsFail()
    locks = AsyncLocks(backend)
    finished = False

    async def hold() -> None:
        nonlocal finished
        async with locks.lock("job", ttl=0.06):
            backend.down = True
            await asyncio.sleep(1)
            finished = True

    with pytest.raises(LockLostError):
        await hold()

    assert not finished


async def test_a_lock_of_two_holders_takes_two_and_refuses_a_third(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    first = await call(locks.try_lock, "export", ttl=10, holders=2)
    second = await call(locks.try_lock, "export", ttl=10, holders=2)

    third = await call(locks.try_lock, "export", ttl=10, holders=2)

    assert first is not None
    assert second is not None
    assert third is None


async def test_a_holder_that_leaves_frees_its_place(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    leaving = await call(locks.try_lock, "export", ttl=10, holders=2)
    await call(locks.try_lock, "export", ttl=10, holders=2)
    assert leaving is not None

    await run_block(leaving)

    assert await call(locks.try_lock, "export", ttl=10, holders=2) is not None


@pytest.mark.no_leaks(threads=False, blocking_threshold=LOOP_BLOCK_SECONDS)
@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_locked_runs_as_many_calls_at_once_as_it_has_holders(new_process_locks: NewLocks) -> None:
    locks = new_process_locks()
    assert isinstance(locks, AsyncLocks)
    running = peak = 0
    both_in = asyncio.Event()

    @locks.locked(ttl=10, holders=2)
    async def export(report_id: int) -> int:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        if running == 2:
            both_in.set()
        await asyncio.wait_for(both_in.wait(), timeout=5)  # the second holder, however slow the backend
        await asyncio.sleep(0.05)  # a third one inside, if the lock let it in, is counted meanwhile
        running -= 1
        return report_id

    exported = await asyncio.gather(*(export(report_id) for report_id in range(5)))

    assert exported == [0, 1, 2, 3, 4]
    assert peak == 2


def test_every_holder_of_a_lock_is_extended() -> None:
    locks = Locks(MemoryBackend())

    with locks.lock("export", ttl=0.15, holders=2), locks.lock("export", ttl=0.15, holders=2):
        time.sleep(0.3)  # twice the ttl: only extensions keep both places
        held = locks.try_lock("export", ttl=1, holders=2)

    assert held is None


def test_a_lock_of_no_holders_is_refused() -> None:
    locks = Locks(MemoryBackend())

    with pytest.raises(InvalidOptionsError, match="holders is 0"):
        locks.lock("export", ttl=10, holders=0)


def test_a_lock_entered_again_is_extended_again() -> None:
    locks = Locks(MemoryBackend())
    lock = locks.lock("job", ttl=0.15)
    with lock:
        pass

    with lock:
        time.sleep(0.3)  # twice the ttl: only extensions keep it
        held = locks.try_lock("job", ttl=1)

    assert held is None


async def test_an_async_lock_entered_again_is_still_cancelled_when_lost() -> None:
    backend = _AsyncExtensionsFail()
    lock = AsyncLocks(backend).lock("job", ttl=0.06)
    async with lock:
        pass

    async def hold() -> None:
        async with lock:
            backend.down = True
            await asyncio.sleep(1)

    with pytest.raises(LockLostError):
        await hold()


def test_a_lock_keeps_apart_from_a_cached_function_of_the_same_key() -> None:
    backend = MemoryBackend()
    cache, locks = Cache(backend), Locks(backend)
    loads = 0

    @locks.locked(ttl=30, timeout=0.2)  # the default keys of both are the name of the function
    @cache(ttl=60)
    def report() -> int:
        nonlocal loads
        loads += 1
        return loads

    reports = [report(), report(), report()]

    assert reports == [1, 1, 1]


# Rate limits


async def test_a_fixed_window_refuses_calls_over_it_for_its_ban(new_process_limiter: NewLimiter) -> None:
    limiter = new_process_limiter()
    limit = FixedWindow(calls=2, per=60, ban_for=120)
    await call(limiter.count, "api", limit)
    await call(limiter.count, "api", limit)

    with pytest.raises(RateLimitedError) as refused:
        await call(limiter.count, "api", limit)

    assert refused.value.retry_after == 120


async def test_a_sliding_window_refuses_calls_over_it(new_process_limiter: NewLimiter, clock: Clock) -> None:
    clock.now = 1000.0  # the start of a window of one second
    limiter = new_process_limiter(clock=clock)
    for _ in range(3):
        await call(limiter.count, "api", SlidingWindow.per_second(3))

    with pytest.raises(RateLimitedError) as refused:
        await call(limiter.count, "api", SlidingWindow.per_second(3))

    assert 0 < refused.value.retry_after <= 2


async def test_a_sliding_window_lets_calls_through_once_it_passed(
    new_process_limiter: NewLimiter, clock: Clock
) -> None:
    clock.now = 1000.0  # the start of a window of one second
    limiter = new_process_limiter(clock=clock)
    for _ in range(3):
        await call(limiter.count, "api", SlidingWindow.per_second(3))

    clock.now += 2  # both windows are past
    state = await call(limiter.count, "api", SlidingWindow.per_second(3))

    assert state is not None
    assert state.remaining == 2


async def test_limits_on_one_key_count_apart(new_process_limiter: NewLimiter, clock: Clock) -> None:
    clock.now = 1_000_000.0  # at the start of a window, so the last one does not weigh
    limiter = new_process_limiter(clock=clock)
    for _ in range(3):
        await call(limiter.count, "ip:1", SlidingWindow(calls=100, per=60))
        await call(limiter.count, "user:1", FixedWindow(calls=100, per=60))

    sliding = await call(limiter.count, "ip:1", SlidingWindow(calls=5, per=60))
    fixed = await call(limiter.count, "user:1", FixedWindow(calls=3, per=3600))

    assert sliding is not None
    assert fixed is not None
    assert (sliding.remaining, fixed.remaining) == (4, 2)


async def test_the_state_of_a_sliding_window(new_process_limiter: NewLimiter, clock: Clock) -> None:
    clock.now = 1_000_000.0  # at the start of a window, so the last one does not weigh
    limiter = new_process_limiter(clock=clock)

    first = await call(limiter.count, "api", SlidingWindow.per_second(3))
    second = await call(limiter.count, "api", SlidingWindow.per_second(3), cost=2)

    assert first is not None
    assert second is not None
    assert (first.limit, first.remaining) == (3, 2)
    assert second.remaining == 0
    assert 0 < second.reset_after <= 1


async def test_the_state_of_a_fixed_window(new_process_limiter: NewLimiter) -> None:
    limiter = new_process_limiter()

    state = await call(limiter.count, "login", FixedWindow(calls=5, per=60), cost=3)

    assert state is not None
    assert state.remaining == 2
    assert 59 < state.reset_after <= 60


async def test_a_cost_over_the_limit_is_refused(new_process_limiter: NewLimiter) -> None:
    limiter = new_process_limiter()

    with pytest.raises(InvalidOptionsError):
        await call(limiter.count, "api", SlidingWindow.per_second(3), cost=4)


class _CloseFails(MemoryBackend):
    __slots__ = ()

    @override
    def close(self) -> None:
        msg = "the backend is down"
        raise BackendError(msg)


class _RecordsClose(MemoryBackend):
    __slots__ = ("closed",)

    def __init__(self) -> None:
        super().__init__()

        self.closed = False

    @override
    def close(self) -> None:
        self.closed = True
        super().close()


def test_closing_a_cache_closes_the_fallback_when_the_backend_fails_to_close() -> None:
    fallback = _RecordsClose()
    cache = Cache(_CloseFails(), fallback=Fallback(fallback))

    with pytest.raises(BackendError):
        cache.close()

    assert fallback.closed


class _UndoFails(MemoryBackend):
    # the backend fails to take back the count of a refused call
    __slots__ = ()

    @override
    def incr(
        self,
        key: str,
        by: int,
        /,
        *,
        ttl: float | None = None,
    ) -> int:
        if by < 0:
            msg = "the backend is down"
            raise BackendError(msg)
        return super().incr(key, by, ttl=ttl)


def test_a_call_over_the_limit_is_refused_when_taking_back_its_count_fails() -> None:
    hook = RecordingHook()
    limiter = RateLimiter(_UndoFails(), hooks=[hook])
    limit = SlidingWindow(calls=1, per=60)
    limiter.count("api", limit)

    with pytest.raises(RateLimitedError):
        limiter.count("api", limit)

    assert [(failure.operation, type(failure.error)) for failure in hook.failures] == [
        (Operation.RATE_LIMIT, BackendError)
    ]


@pytest.mark.filterwarnings("ignore::pashe.errors.OneProcessWarning")  # a memory backend stands for the shared server
def test_a_hook_of_on_call_and_on_error_alone_hears_rate_limits_and_near_reads() -> None:
    hook = RecordingHook()  # leaves on_rate_limit, on_near_read and on_near_flush as Hook has them
    limiter = RateLimiter(NearCacheBackend(MemoryBackend(), MemoryBackend(), hooks=[hook]), hooks=[hook])

    state = limiter.count("ip", FixedWindow(calls=2, per=60, ban_for=60))

    assert state is not None
    assert state.remaining == 1
    assert hook.failures == []
