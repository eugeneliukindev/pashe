"""locked and rate_limited: every call of a function inside a lock or a limit."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from pashe import AsyncCache, Cache
from pashe.backends import AsyncMemoryBackend, MemoryBackend
from pashe.errors import RateLimitedError
from pashe.ratelimit import FixedWindow


def test_locked_runs_calls_of_one_key_one_at_a_time() -> None:
    cache = Cache(MemoryBackend())
    running = peak = 0
    guard = threading.Lock()

    @cache.locked(ttl=5, key="report:{report_id}")
    def build(report_id: int) -> int:
        nonlocal running, peak
        with guard:
            running += 1
            peak = max(peak, running)
        time.sleep(0.02)
        with guard:
            running -= 1
        return report_id

    threads = [threading.Thread(target=build, args=(1,)) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert peak == 1


async def test_async_locked_runs_calls_of_one_key_one_at_a_time() -> None:
    cache = AsyncCache(AsyncMemoryBackend())
    order: list[str] = []

    @cache.locked(ttl=5)
    async def build(name: str) -> None:
        order.append(name)
        await asyncio.sleep(0.01)
        order.append(name)

    await asyncio.gather(build("a"), build("b"))
    assert order in (["a", "a", "b", "b"], ["b", "b", "a", "a"])  # one lock for the function


def test_rate_limited_counts_calls_per_key() -> None:
    cache = Cache(MemoryBackend())

    @cache.rate_limited(FixedWindow(calls=2, per=60), key="api:{user_id}")
    def call_api(user_id: int) -> int:
        return user_id

    assert [call_api(1), call_api(1)] == [1, 1]
    with pytest.raises(RateLimitedError):
        call_api(1)
    assert call_api(2) == 2  # another user, another limit


async def test_async_rate_limited() -> None:
    cache = AsyncCache(AsyncMemoryBackend())

    @cache.rate_limited(FixedWindow(calls=1, per=60))
    async def call_api() -> str:
        return "ok"

    assert await call_api() == "ok"
    with pytest.raises(RateLimitedError):
        await call_api()


def test_decorated_methods_keep_working() -> None:
    cache = Cache(MemoryBackend())

    class Reports:
        @cache.locked(ttl=5, key="report:{report_id}")
        def build(self, report_id: int) -> int:
            return report_id * 10

    assert Reports().build(4) == 40


def test_a_function_of_the_other_kind_is_refused() -> None:
    async def aload() -> None:
        return None

    def load() -> None:
        return None

    with pytest.raises(TypeError, match="AsyncCache"):
        Cache(MemoryBackend()).locked(ttl=5)(aload)
    with pytest.raises(TypeError, match="Cache"):
        AsyncCache(AsyncMemoryBackend()).locked(ttl=5)(load)  # type: ignore[arg-type]
