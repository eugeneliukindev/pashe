"""The contract every backend keeps; it never waits for real time to pass."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest
from redis import Redis

from pashe.backends import Backend
from pashe.contrib.redis import RedisBackend
from pashe.errors import InvalidOptionsError, WrongTypeError
from tests.harness.stores import SERVED, STORE_PARAMS, STORES

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from pashe.backends import AsyncBackend
    from tests.harness.helpers import EitherBackend, Side

_INT64_MAX = 2**63 - 1


class _AwaitSync:
    """Drives a sync backend through these async tests: every method becomes a coroutine."""

    __slots__ = ("_backend",)

    def __init__(self, backend: Backend) -> None:
        self._backend = backend

    def __getattr__(self, name: str) -> Callable[..., object]:
        method = getattr(self._backend, "close" if name == "aclose" else name)
        if name == "scan":

            async def scan(pattern: str) -> AsyncIterator[str]:
                for key in method(pattern):
                    yield key

            return scan

        async def call(*args: object, **kwargs: object) -> object:
            return method(*args, **kwargs)

        return call


def _awaited(backend: Backend) -> AsyncBackend:
    """Drive backend, of the sync side, through these async tests."""
    return _AwaitSync(backend)  # type: ignore[return-value]  # every method of AsyncBackend, made of the sync one


@pytest.fixture(params=[*STORE_PARAMS, "near"])
async def backend(request: pytest.FixtureRequest, side: Side, key_prefix: str) -> AsyncIterator[AsyncBackend]:
    """An empty backend of every store and side, and a near cache over memory."""
    if request.param == "near":
        created: EitherBackend = side.near()
    else:
        created = STORES[request.param](request, side)()
    if request.param in SERVED:
        # The tests of a process share its server, and every process shares the cluster, which has one
        # database: each test keeps its keys under a prefix of its own, so its keys still spread over
        # the slots, and so over the nodes.
        created = side.prefixed(created, key_prefix)
    driven = _awaited(created) if isinstance(created, Backend) else created

    yield driven
    await driven.aclose()


def test_redis_needs_bytes() -> None:
    with pytest.raises(InvalidOptionsError):
        RedisBackend(Redis(decode_responses=True))


async def test_get_set(backend: AsyncBackend) -> None:
    await backend.set("k", b"v")
    await backend.set("empty", b"")
    assert await backend.get("k") == b"v"
    assert await backend.get("empty") == b""
    assert await backend.get("missing") is None
    await backend.ping()


async def test_get_many(backend: AsyncBackend) -> None:
    await backend.set("a", b"1")
    await backend.set("c", b"3")
    assert await backend.get_many(["a", "b", "c"]) == [b"1", None, b"3"]
    assert await backend.get_many([]) == []


async def test_set_many(backend: AsyncBackend) -> None:
    await backend.set_many({"a": b"1", "b": b"2"}, ttl=3600)
    for key in ("a", "b"):
        left = await backend.ttl(key)
        assert left is not None
        assert 0 < left <= 3600


async def test_set_if_absent(backend: AsyncBackend) -> None:
    assert await backend.set_if_absent("k", b"1")
    assert not await backend.set_if_absent("k", b"2")
    assert await backend.get("k") == b"1"


async def test_set_replaces_ttl(backend: AsyncBackend) -> None:
    await backend.set("k", b"1", ttl=3600)
    await backend.set("k", b"2")
    assert await backend.ttl("k") == math.inf


async def test_delete(backend: AsyncBackend) -> None:
    await backend.set_many({"a": b"1", "b": b"1", "c": b"1"})
    assert await backend.delete("a")
    assert not await backend.delete("a")
    assert await backend.get_many(["a", "b", "c"]) == [None, b"1", b"1"]


async def test_incr(backend: AsyncBackend) -> None:
    assert await backend.incr("n", 5) == 5
    assert await backend.incr("n", -7) == -2
    assert await backend.get("n") == b"-2"
    await backend.set("m", b"40")
    assert await backend.incr("m", 2) == 42


async def test_incr_ttl_only_on_create(backend: AsyncBackend) -> None:
    await backend.incr("n", 1, ttl=60)
    await backend.incr("n", 1, ttl=3600)
    left = await backend.ttl("n")
    assert left is not None
    assert 0 < left <= 60
    await backend.incr("plain", 1)
    assert await backend.ttl("plain") == math.inf


async def test_incr_errors(backend: AsyncBackend) -> None:
    await backend.set("json", b'{"a":1}')
    with pytest.raises(WrongTypeError):
        await backend.incr("json", 1)
    await backend.set("padded", b"01")  # Redis takes no leading 0
    with pytest.raises(WrongTypeError):
        await backend.incr("padded", 1)
    await backend.incr("max", _INT64_MAX)
    with pytest.raises(OverflowError):
        await backend.incr("max", 1)
    assert await backend.get("max") == str(_INT64_MAX).encode()


async def test_expire_and_ttl(backend: AsyncBackend) -> None:
    assert await backend.ttl("missing") is None
    await backend.set("k", b"1")
    assert await backend.ttl("k") == math.inf
    assert await backend.expire("k", 60)
    left = await backend.ttl("k")
    assert left is not None
    assert 0 < left <= 60
    assert not await backend.expire("missing", 60)


async def test_delete_if_equals(backend: AsyncBackend) -> None:
    assert await backend.set_if_absent("lock", b"me", ttl=60)
    assert not await backend.delete_if_equals("lock", b"other")
    assert await backend.delete_if_equals("lock", b"me")
    assert await backend.get("lock") is None
    assert not await backend.delete_if_equals("lock", b"me")


async def test_expire_if_equals(backend: AsyncBackend) -> None:
    assert not await backend.expire_if_equals("lock", b"me", 3600)
    await backend.set("lock", b"me", ttl=60)
    assert not await backend.expire_if_equals("lock", b"other", 3600)
    left = await backend.ttl("lock")
    assert left is not None
    assert left <= 60
    assert await backend.expire_if_equals("lock", b"me", 3600)
    left = await backend.ttl("lock")
    assert left is not None
    assert 60 < left <= 3600
