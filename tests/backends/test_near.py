"""Near caches of several processes over one shared backend: when a copy answers and when it is dropped."""

from __future__ import annotations

import asyncio
import time
import warnings
from typing import TYPE_CHECKING, override

import pytest
import redis.asyncio
from redis import Redis, ResponseError
from redis.cluster import RedisCluster

from pashe import Cache
from pashe._internal.redis.listening import tracking_command
from pashe._internal.redis.messages import read_invalidation
from pashe.backends import (
    AsyncMemcachedBackend,
    AsyncMemoryBackend,
    AsyncNearCacheBackend,
    Backend,
    MemcachedBackend,
    MemoryBackend,
    NearCacheBackend,
    SQLiteBackend,
)
from pashe.contrib.redis import (
    AsyncRedisBackend,
    AsyncRedisPubSubBus,
    AsyncRedisTrackingBus,
    RedisBackend,
    RedisPubSubBus,
    RedisTrackingBus,
)
from pashe.errors import BackendError, InvalidOptionsError, OneProcessWarning
from pashe.hooks import Hook, Operation
from pashe.invalidation import InvalidationBus
from pashe.options import Fallback
from tests.harness.helpers import MemoryBus, RecordingHook

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from pashe.hooks import Failure
    from pashe.invalidation import InvalidationHandler

# A memory backend stands for the shared server here, as two near caches over one stand for two processes
pytestmark = pytest.mark.filterwarnings("ignore::pashe.errors.OneProcessWarning")

_WAIT = 5.0  # seconds a message may take through Redis
# the async RedisCluster of redis-py has pub/sub from version 8, which the lowest versions run without
_ASYNC_CLUSTER_PUB_SUB = pytest.mark.skipif(
    not hasattr(redis.asyncio.RedisCluster, "pubsub"), reason="the async RedisCluster of this redis-py has no pub/sub"
)


def test_a_copy_answers_until_a_write_drops_it() -> None:
    shared = MemoryBackend()
    near = NearCacheBackend(MemoryBackend(), shared)
    shared.set("k", b"1")
    assert near.get("k") == b"1"
    shared.set("k", b"2")
    assert near.get("k") == b"1"
    near.set("k", b"3")
    assert near.get("k") == b"3"
    assert near.get_many(["k", "missing"]) == [b"3", None]


def test_a_bus_drops_the_copies_of_other_processes() -> None:
    shared, wire = MemoryBackend(), MemoryBus()
    first = NearCacheBackend(MemoryBackend(), shared, bus=wire)
    second = NearCacheBackend(MemoryBackend(), shared, bus=wire)
    first.set("k", b"1")
    assert second.get("k") == b"1"
    first.set("k", b"2")
    assert second.get("k") == b"2"
    second.get("other")
    first.delete("k")
    assert second.get("k") is None
    second.get("other")
    wire.publish(None)
    shared.set("other", b"3")
    assert second.get("other") == b"3"
    first.close()
    second.close()
    assert not wire.listeners


def test_local_ttl_must_be_positive() -> None:
    with pytest.raises(InvalidOptionsError):
        NearCacheBackend(MemoryBackend(), MemoryBackend(), local_ttl=0)


def test_redis_bus(redis_url: str) -> None:
    with Redis.from_url(redis_url, socket_timeout=1) as admin:
        admin.flushdb()
    clients = [Redis.from_url(redis_url, socket_timeout=1) for _ in range(2)]
    first, second = (
        NearCacheBackend(MemoryBackend(), RedisBackend(client), bus=RedisPubSubBus(client, channel=redis_url))
        for client in clients
    )
    first.set("k", b"1")
    assert second.get("k") == b"1"
    first.set("k", b"2")
    deadline = time.monotonic() + _WAIT
    while second.get("k") != b"2" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert second.get("k") == b"2"
    first.close()
    second.close()


async def test_async_redis_bus(redis_url: str) -> None:
    async with redis.asyncio.Redis.from_url(redis_url, socket_timeout=1) as admin:
        await admin.flushdb()
    clients = [redis.asyncio.Redis.from_url(redis_url, socket_timeout=1) for _ in range(2)]
    first, second = (
        AsyncNearCacheBackend(
            AsyncMemoryBackend(), AsyncRedisBackend(client), bus=AsyncRedisPubSubBus(client, channel=redis_url)
        )
        for client in clients
    )
    await first.set("k", b"1")
    assert await second.get("k") == b"1"
    await asyncio.sleep(0.1)  # the listener of second subscribes on its first read
    await first.set("k", b"2")
    async with asyncio.timeout(_WAIT):
        while await second.get("k") != b"2":  # noqa: ASYNC110 - polls what a message from Redis changes
            await asyncio.sleep(0.01)
    await first.aclose()
    await second.aclose()


def test_a_pub_sub_bus_over_a_cluster(redis_cluster_url: str, key_prefix: str) -> None:
    clients = [RedisCluster.from_url(redis_cluster_url, socket_timeout=1) for _ in range(2)]
    first, second = (
        NearCacheBackend(MemoryBackend(), RedisBackend(client), bus=RedisPubSubBus(client, channel=key_prefix))
        for client in clients
    )
    key = f"{key_prefix}k"
    first.set(key, b"1")
    assert second.get(key) == b"1"

    first.set(key, b"2")
    deadline = time.monotonic() + _WAIT
    while second.get(key) != b"2" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert second.get(key) == b"2"
    first.close()
    second.close()


@_ASYNC_CLUSTER_PUB_SUB
async def test_an_async_pub_sub_bus_over_a_cluster(redis_cluster_url: str, key_prefix: str) -> None:
    clients = [redis.asyncio.RedisCluster.from_url(redis_cluster_url, socket_timeout=1) for _ in range(2)]
    first, second = (
        AsyncNearCacheBackend(
            AsyncMemoryBackend(), AsyncRedisBackend(client), bus=AsyncRedisPubSubBus(client, channel=key_prefix)
        )
        for client in clients
    )
    key = f"{key_prefix}k"
    await first.set(key, b"1")
    assert await second.get(key) == b"1"
    await asyncio.sleep(0.1)  # the listener of second subscribes on its first read

    await first.set(key, b"2")
    async with asyncio.timeout(_WAIT):
        while await second.get(key) != b"2":  # noqa: ASYNC110 - polls what a message from Redis changes
            await asyncio.sleep(0.01)
    await first.aclose()
    await second.aclose()


@_ASYNC_CLUSTER_PUB_SUB
async def test_an_async_pub_sub_bus_listens_over_a_cluster_it_has_not_used_yet(
    redis_cluster_url: str, key_prefix: str
) -> None:
    client = redis.asyncio.RedisCluster.from_url(redis_cluster_url, socket_timeout=1)
    bus = AsyncRedisPubSubBus(client, channel=key_prefix)
    heard: list[list[str] | None] = []

    async def on_invalidate(keys: list[str] | None) -> None:
        heard.append(keys)

    stop = bus.listen(AsyncMemoryBackend(), on_invalidate)  # before any command of the client; pub/sub leaves shared

    async with asyncio.timeout(_WAIT):
        while ["k"] not in heard:
            await bus.publish(["k"])
            await asyncio.sleep(0.05)
    await stop()
    await client.aclose()


def test_a_pub_sub_bus_refuses_an_async_cluster_without_pub_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(redis.asyncio.RedisCluster, "pubsub", raising=False)  # as in redis-py before 8
    client = redis.asyncio.RedisCluster(host="localhost", port=6379)  # connects at its first command, never here

    with pytest.raises(InvalidOptionsError, match="redis-py 8 or later"):
        AsyncRedisPubSubBus(client)


def test_a_near_cache_over_a_backend_of_this_process_warns() -> None:
    with pytest.warns(OneProcessWarning, match="the copies add nothing"):
        NearCacheBackend(MemoryBackend(), MemoryBackend())


def test_a_near_cache_over_a_backend_other_processes_see_is_taken_as_it_is(tmp_path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the test
        near = NearCacheBackend(MemoryBackend(), SQLiteBackend(tmp_path / "cache.db"))

    assert near.shared_by_processes
    near.close()


@pytest.mark.parametrize("make", [MemoryBackend, lambda: SQLiteBackend(":memory:")], ids=["memory", "sqlite in memory"])
def test_a_backend_of_this_process_says_so(make: Callable[[], Backend]) -> None:
    backend = make()

    assert not backend.shared_by_processes
    backend.close()


def test_a_backend_over_a_server_is_seen_by_other_processes() -> None:
    assert MemcachedBackend("localhost").shared_by_processes  # connects at its first call, never here


def test_a_tracking_bus_refuses_a_backend_that_never_writes_to_redis() -> None:
    with pytest.raises(TypeError, match="shared must be RedisBackend, not MemcachedBackend"):
        NearCacheBackend(MemoryBackend(), MemcachedBackend(), bus=RedisTrackingBus())  # type: ignore[misc]  # as a caller without types
    with pytest.raises(TypeError, match="shared must be AsyncRedisBackend, not AsyncMemcachedBackend"):
        AsyncNearCacheBackend(AsyncMemoryBackend(), AsyncMemcachedBackend(), bus=AsyncRedisTrackingBus())  # type: ignore[misc]  # as above


def test_a_near_cache_refuses_a_tracking_bus_over_a_cluster(redis_cluster_url: str) -> None:
    backend = RedisBackend(RedisCluster.from_url(redis_cluster_url, socket_timeout=1))  # connects to the nodes already

    with pytest.raises(InvalidOptionsError, match="over a Redis Cluster"):
        NearCacheBackend(MemoryBackend(), backend, bus=RedisTrackingBus())
    backend.close()
    async_backend = AsyncRedisBackend(redis.asyncio.RedisCluster.from_url(redis_cluster_url, socket_timeout=1))
    with pytest.raises(InvalidOptionsError, match="over a Redis Cluster"):
        AsyncNearCacheBackend(AsyncMemoryBackend(), async_backend, bus=AsyncRedisTrackingBus())


@pytest.fixture
def tracking_prefix(redis_url: str) -> str:
    """A prefix of keys only this test writes; skips a server without CLIENT TRACKING, such as some clones of Redis."""
    client = Redis.from_url(redis_url, socket_timeout=1)
    try:
        client.client_tracking_on(prefix=["probe:"], bcast=True)
    except ResponseError as error:
        pytest.skip(f"the server has no CLIENT TRACKING: {error}")
    finally:
        client.close()
    return f"tracked:{redis_url.rsplit('/', 1)[-1]}:"  # tracking is per server, not per database


def test_redis_tracking_bus_drops_copies_of_any_write(redis_url: str, tracking_prefix: str) -> None:
    clients = [Redis.from_url(redis_url, socket_timeout=1) for _ in range(2)]
    first, second = (
        NearCacheBackend(MemoryBackend(), shared, bus=RedisTrackingBus(prefix=tracking_prefix))
        for shared in (RedisBackend(client) for client in clients)
    )
    key = f"{tracking_prefix}k"
    first.set(key, b"1")
    assert second.get(key) == b"1"
    time.sleep(0.2)  # the listener of second turns tracking on in a thread of its own
    first.set(key, b"2")
    _wait_for(lambda: second.get(key) == b"2")
    with Redis.from_url(redis_url, socket_timeout=1) as outsider:
        outsider.set(key, b"3")
    _wait_for(lambda: second.get(key) == b"3")
    first.close()
    second.close()


async def test_async_redis_tracking_bus_drops_copies_of_any_write(redis_url: str, tracking_prefix: str) -> None:
    clients = [redis.asyncio.Redis.from_url(redis_url, socket_timeout=1) for _ in range(2)]
    first, second = (
        AsyncNearCacheBackend(AsyncMemoryBackend(), shared, bus=AsyncRedisTrackingBus(prefix=tracking_prefix))
        for shared in (AsyncRedisBackend(client) for client in clients)
    )
    key = f"{tracking_prefix}k"
    await first.set(key, b"1")
    assert await second.get(key) == b"1"
    await asyncio.sleep(0.2)  # the listener of second turns tracking on in a task
    async with redis.asyncio.Redis.from_url(redis_url, socket_timeout=1) as outsider:
        await outsider.set(key, b"3")
    async with asyncio.timeout(_WAIT):
        while await second.get(key) != b"3":  # noqa: ASYNC110 - polls what a message from Redis changes
            await asyncio.sleep(0.01)
    await first.aclose()
    await second.aclose()


def _wait_for(done: Callable[[], bool]) -> None:
    deadline = time.monotonic() + _WAIT
    while not done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done()


class _FlushFails(Hook):
    # a hook with a bug: every drop of every copy raises in the listener of the bus
    __slots__ = ()

    @override
    def on_near_flush(self) -> None:
        msg = "a bug of a hook"
        raise ValueError(msg)


def test_a_redis_pub_sub_bus_tells_an_error_while_it_listens(redis_url: str, key_prefix: str) -> None:
    client = Redis.from_url(redis_url, socket_timeout=1)
    heard = RecordingHook()
    bus = RedisPubSubBus(client, channel=key_prefix, hooks=[heard])
    near = NearCacheBackend(MemoryBackend(), RedisBackend(client), bus=bus, hooks=[_FlushFails()])
    near.get("k")  # starts listening

    RedisPubSubBus(client, channel=key_prefix).publish(None)
    _wait_for(lambda: bool(heard.failures))
    near.close()

    assert (heard.failures[0].operation, type(heard.failures[0].error)) == (Operation.LISTEN, ValueError)


async def test_an_async_redis_pub_sub_bus_tells_an_error_while_it_listens(redis_url: str, key_prefix: str) -> None:
    client = redis.asyncio.Redis.from_url(redis_url, socket_timeout=1)
    heard = RecordingHook()
    bus = AsyncRedisPubSubBus(client, channel=key_prefix, hooks=[heard])
    near = AsyncNearCacheBackend(AsyncMemoryBackend(), AsyncRedisBackend(client), bus=bus, hooks=[_FlushFails()])

    await near.get("k")  # starts listening: the subscription drops every copy
    async with asyncio.timeout(_WAIT):
        while not heard.failures:  # noqa: ASYNC110 - polls what the task of the listener records
            await asyncio.sleep(0.01)
    await near.aclose()

    assert (heard.failures[0].operation, type(heard.failures[0].error)) == (Operation.LISTEN, ValueError)


class _CountsFlushes(Hook):
    __slots__ = ("flushes",)

    def __init__(self) -> None:
        self.flushes = 0

    @override
    def on_near_flush(self) -> None:
        self.flushes += 1


async def test_an_async_redis_pub_sub_bus_keeps_its_copies_through_a_quiet_longer_than_socket_timeout(
    redis_url: str,
    key_prefix: str,
) -> None:
    client = redis.asyncio.Redis.from_url(redis_url, socket_timeout=0.1)
    counted = _CountsFlushes()
    bus = AsyncRedisPubSubBus(client, channel=key_prefix)
    near = AsyncNearCacheBackend(AsyncMemoryBackend(), AsyncRedisBackend(client), bus=bus, hooks=[counted])

    await near.get("k")  # starts listening: the subscription drops every copy, once
    await asyncio.sleep(0.5)  # no message: a read that failed after socket_timeout would drop them again
    await near.aclose()

    assert counted.flushes == 1


def test_a_write_that_changes_nothing_is_not_published() -> None:
    sent: list[list[str] | None] = []

    class Counting(MemoryBus):
        @override
        def publish(self, keys: Sequence[str] | None, /) -> None:
            sent.append(None if keys is None else list(keys))

    near = NearCacheBackend(MemoryBackend(), MemoryBackend(), bus=Counting())
    assert near.set_if_absent("lock", b"me", ttl=10)
    assert not near.set_if_absent("lock", b"other", ttl=10)
    assert not near.delete_if_equals("lock", b"other")
    assert not near.delete("missing")
    assert near.delete_if_equals("lock", b"me")
    assert sent == [["lock"], ["lock"]]


def test_a_pub_sub_bus_over_a_redis_that_is_down_lets_the_cache_answer() -> None:
    # nothing listens on port 1
    client = Redis(host="127.0.0.1", port=1, socket_timeout=0.2, socket_connect_timeout=0.2)
    failures: list[Failure] = []
    near = NearCacheBackend(MemoryBackend(), RedisBackend(client), bus=RedisPubSubBus(client))
    cache = Cache(near, hooks=[RecordingHook(failures=failures)], fallback=Fallback(MemoryBackend()))

    @cache(ttl=60)
    def answer() -> int:
        return 42

    assert answer() == 42
    assert all(isinstance(failure.error, BackendError) for failure in failures)
    assert failures


def test_near_caches_that_share_a_pub_sub_bus_hear_every_write_of_each_other(redis_url: str, key_prefix: str) -> None:
    client = Redis.from_url(redis_url, socket_timeout=1)
    bus = RedisPubSubBus(client, channel=key_prefix)
    heard_mine: list[list[str] | None] = []
    heard_theirs: list[list[str] | None] = []
    stops = [bus.listen(MemoryBackend(), heard.append) for heard in (heard_mine, heard_theirs)]  # pub/sub leaves shared

    bus.publish(["k"])
    deadline = time.monotonic() + _WAIT
    while not (["k"] in heard_mine and ["k"] in heard_theirs) and time.monotonic() < deadline:
        time.sleep(0.01)

    assert ["k"] in heard_theirs
    assert ["k"] in heard_mine  # its own too: the copy of the writer goes, and is read again
    for stop in stops:
        stop()
    client.close()


class _Flaky(InvalidationBus[Backend]):
    """A bus whose next publish fails while down is set; it keeps what went through."""

    def __init__(self) -> None:
        self.down = False
        self.sent: list[list[str] | None] = []

    @override
    def publish(self, keys: Sequence[str] | None, /) -> None:
        if self.down:
            msg = "the bus is down"
            raise BackendError(msg)
        self.sent.append(None if keys is None else list(keys))

    @override
    def listen(self, shared: Backend, on_invalidate: InvalidationHandler, /) -> Callable[[], None]:
        return lambda: None


def test_a_drop_the_bus_missed_drops_every_copy_of_the_others_once_it_works() -> None:
    bus = _Flaky()
    near = NearCacheBackend(MemoryBackend(), MemoryBackend(), bus=bus)
    bus.down = True
    near.set("a", b"1")

    bus.down = False
    near.set("b", b"1")
    near.set("c", b"1")

    assert bus.sent == [None, ["b"], ["c"]]


def test_a_publish_that_fails_goes_to_the_hooks() -> None:
    bus, hook = _Flaky(), RecordingHook()
    near = NearCacheBackend(MemoryBackend(), MemoryBackend(), bus=bus, hooks=[hook])
    bus.down = True

    near.set("a", b"1")

    assert [(failure.operation, failure.key) for failure in hook.failures] == [(Operation.PUBLISH, "a")]


@pytest.mark.parametrize(
    ("received", "read"),
    [
        ([b"message", b"__redis__:invalidate", [b"k1", b"k2"]], (True, ["k1", "k2"])),
        ([b"message", b"__redis__:invalidate", None], (True, None)),  # every key, as after FLUSHALL
        ([b"message", b"__redis__:invalidate"], (True, None)),  # cut short: every copy goes
        ([b"message", b"__redis__:invalidate", [b"k", 7]], (True, None)),
        ([b"subscribe", b"__redis__:invalidate", 1], (False, None)),  # the reply to SUBSCRIBE
        (b"OK", (False, None)),
    ],
    ids=["keys", "every key", "cut short", "a key not of bytes", "subscribe", "a reply"],
)
def test_a_reply_of_tracking_is_read_whole_and_one_pashe_cannot_read_drops_every_copy(
    received: object, read: tuple[bool, list[str] | None]
) -> None:
    assert read_invalidation(received) == read


def test_tracking_refuses_a_reply_to_client_id_that_is_not_the_id_of_a_connection() -> None:
    with pytest.raises(ResponseError, match="CLIENT ID answered"):
        tracking_command(b"7", "app:")


class _DroppedWhileCopied(MemoryBackend):
    """A local backend over which a drop of another thread lands while a copy is being stored."""

    def __init__(self, wire: MemoryBus) -> None:
        super().__init__()

        self.wire = wire

    @override
    def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        self.wire.publish([key])  # the listener thread drops key before this copy is stored
        super().set(key, value, ttl=ttl)


def test_a_drop_that_lands_during_a_copy_leaves_no_stale_copy() -> None:
    wire, shared = MemoryBus(), MemoryBackend()
    local = _DroppedWhileCopied(wire)
    near = NearCacheBackend(local, shared, bus=wire)
    shared.set("k", b"old")

    near.get("k")

    assert local.get("k") is None


def _write_while_disconnected(
    redis_url: str,
    name: str,
    key: str,
) -> None:
    """Drop the pub/sub connection of the client named name and write key at once, so its message is lost."""
    with Redis.from_url(redis_url, socket_timeout=1) as admin:
        [listener] = [client["id"] for client in admin.client_list(_type="pubsub") if client["name"] == name]
        with admin.pipeline(transaction=True) as both:
            both.client_kill_filter(_id=listener)
            both.set(key, b"new")
            both.execute()


def test_a_pub_sub_bus_that_reconnects_on_its_own_drops_every_copy(redis_url: str, key_prefix: str) -> None:
    client = Redis.from_url(redis_url, client_name=key_prefix, socket_timeout=1)
    near = NearCacheBackend(
        MemoryBackend(), RedisBackend(client), local_ttl=60, bus=RedisPubSubBus(client, channel=key_prefix)
    )
    key = f"{key_prefix}k"
    client.set(key, b"old")
    assert near.get(key) == b"old"
    time.sleep(1.5)  # the listener waits on the socket, past the reconnect of its first read

    _write_while_disconnected(redis_url, key_prefix, key)

    _wait_for(lambda: near.get(key) == b"new")
    near.close()


async def test_an_async_pub_sub_bus_that_reconnects_on_its_own_drops_every_copy(
    redis_url: str, key_prefix: str
) -> None:
    client = redis.asyncio.Redis.from_url(redis_url, client_name=key_prefix, socket_timeout=1)
    near = AsyncNearCacheBackend(
        AsyncMemoryBackend(),
        AsyncRedisBackend(client),
        local_ttl=60,
        bus=AsyncRedisPubSubBus(client, channel=key_prefix),
    )
    key = f"{key_prefix}k"
    await client.set(key, b"old")
    assert await near.get(key) == b"old"
    await asyncio.sleep(1.5)  # the listener subscribes on the first read, then waits on the socket

    _write_while_disconnected(redis_url, key_prefix, key)

    async with asyncio.timeout(_WAIT):
        while await near.get(key) != b"new":  # noqa: ASYNC110 - polls what the reconnect changes
            await asyncio.sleep(0.01)
    await near.aclose()
