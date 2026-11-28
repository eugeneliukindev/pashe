"""What the memcached backend does past the contract every backend passes: keys, TTLs and failures."""

from __future__ import annotations

import asyncio
import socket
import socketserver
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, override

import pytest

from pashe.backends import AsyncMemcachedBackend, MemcachedBackend
from pashe.errors import BackendError, InvalidOptionsError
from tests.harness.helpers import call, close, open_sockets

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from tests.harness.helpers import EitherBackend, Side

_DAY = 24 * 3600


@pytest.fixture
async def backend(side: Side, memcached_address: tuple[str, int]) -> AsyncIterator[EitherBackend]:
    """A backend of the side over the memcached of this test process, closed however the test ends."""
    created = side.memcached(*memcached_address)
    yield created
    await close(created)


@pytest.fixture
def silent_port() -> Iterator[int]:
    """A port that takes connections and never answers, as a memcached that hangs."""
    with socket.socket() as listening:
        listening.bind(("127.0.0.1", 0))
        listening.listen()
        yield listening.getsockname()[1]


class _AnswersOnceThenHangsUp(socketserver.StreamRequestHandler):
    """A memcached that answers one mn on a connection and closes it, as one that restarted."""

    @override
    def handle(self) -> None:
        self.rfile.readline()
        self.wfile.write(b"MN\r\n")


@pytest.fixture
def hanging_up_port() -> Iterator[int]:
    """A port whose server closes every connection after its first answer."""
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _AnswersOnceThenHangsUp) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield server.server_address[1]
        server.shutdown()


class _AnswersByTheByte(socketserver.StreamRequestHandler):
    """A memcached that answers a byte at a time: each byte in time, the whole answer late."""

    @override
    def handle(self) -> None:
        self.rfile.readline()
        for byte in b"VA 5 \r\nhello\r\n":
            self.wfile.write(bytes([byte]))
            self.wfile.flush()
            time.sleep(0.05)


@pytest.fixture
def trickling_port() -> Iterator[int]:
    """A port whose server takes 0.05 s for each byte of an answer."""
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _AnswersByTheByte) as server:
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield server.server_address[1]
        server.shutdown()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port  # closed: nothing listens on it


async def test_a_key_longer_than_memcached_takes_is_kept(backend: EitherBackend, key_prefix: str) -> None:
    long_key = key_prefix + "k" * 300
    await call(backend.set, long_key, b"1")
    await call(backend.set, long_key + "other", b"2")

    found = await call(backend.get_many, [long_key, long_key + "other"])

    assert found == [b"1", b"2"]  # each long key has a digest of its own


async def test_a_ttl_past_30_days_holds_as_long(backend: EitherBackend, key_prefix: str) -> None:
    await call(backend.set, f"{key_prefix}k", b"1", ttl=40 * _DAY)  # memcached reads it as a Unix time

    left = await call(backend.ttl, f"{key_prefix}k")
    assert left is not None
    assert 39 * _DAY < left <= 40 * _DAY + 2  # the clock of memcached ticks whole seconds, up to one behind


@pytest.mark.parametrize("side", ["async"], indirect=True)
async def test_async_counts_from_many_tasks_add_up(backend: AsyncMemcachedBackend, key_prefix: str) -> None:
    counts = await asyncio.gather(*(backend.incr(f"{key_prefix}n", 1) for _ in range(50)))

    assert sorted(counts) == list(range(1, 51))  # each under a CAS token: none lost, none twice


@pytest.mark.parametrize("side", ["sync"], indirect=True)
def test_counts_from_many_threads_add_up(backend: MemcachedBackend, key_prefix: str) -> None:
    with ThreadPoolExecutor(8) as pool:
        counts = list(pool.map(lambda _: backend.incr(f"{key_prefix}n", 1), range(50)))

    assert sorted(counts) == list(range(1, 51))


async def test_a_memcached_that_can_not_be_reached_raises_backend_error(side: Side) -> None:
    backend = side.memcached("127.0.0.1", _free_port())

    with pytest.raises(BackendError, match="can't connect"):
        await call(backend.ping)
    await close(backend)


async def test_a_memcached_that_does_not_answer_raises_backend_error_in_time(side: Side, silent_port: int) -> None:
    backend = (
        AsyncMemcachedBackend("127.0.0.1", port=silent_port, timeout=0.1)
        if side.is_async
        else MemcachedBackend("127.0.0.1", port=silent_port, timeout=0.1)
    )

    with pytest.raises(BackendError):
        await asyncio.wait_for(call(backend.get, "k"), timeout=5)  # the 0.1 s of the backend, not this bound
    await close(backend)


async def test_a_value_too_large_raises_backend_error_and_the_next_call_works(
    backend: EitherBackend,
    key_prefix: str,
) -> None:
    with pytest.raises(BackendError, match="too large"):
        await call(backend.set, f"{key_prefix}big", b"x" * 2_000_000)  # past the 1 MB memcached takes by default

    await call(backend.set, f"{key_prefix}small", b"1")
    assert await call(backend.get, f"{key_prefix}small") == b"1"


def test_a_port_that_is_not_one_is_refused() -> None:
    with pytest.raises(InvalidOptionsError, match="the port of memcached"):
        MemcachedBackend("localhost", port=0)


def test_a_timeout_that_waits_for_nothing_is_refused() -> None:
    with pytest.raises(InvalidOptionsError, match="how long a call waits for memcached"):
        MemcachedBackend("localhost", timeout=0)


async def test_a_connection_memcached_closed_is_not_taken_again(side: Side, hanging_up_port: int) -> None:
    backend = side.memcached("127.0.0.1", hanging_up_port)
    await call(backend.ping)
    await asyncio.sleep(0.1)  # the server closes the connection meanwhile, as memcached does on a restart

    await call(backend.ping)  # over a new connection, not the closed one

    await close(backend)


@pytest.mark.skipif(sys.platform != "linux", reason="counts the open sockets of the process in /proc")
async def test_a_call_after_close_leaves_no_socket_open(side: Side, memcached_address: tuple[str, int]) -> None:
    before = open_sockets()
    backend = side.memcached(*memcached_address)
    await close(backend)

    await call(backend.ping)  # as a call that was still running when the backend closed

    assert open_sockets() == before


async def test_the_timeout_bounds_a_whole_call_however_its_answer_trickles(side: Side, trickling_port: int) -> None:
    backend = (
        AsyncMemcachedBackend("127.0.0.1", port=trickling_port, timeout=0.2)
        if side.is_async
        else MemcachedBackend("127.0.0.1", port=trickling_port, timeout=0.2)
    )
    started = time.monotonic()

    with pytest.raises(BackendError):
        await call(backend.get, "k")  # the answer takes 0.8 s, 0.05 s a byte

    assert time.monotonic() - started < 0.5
    await close(backend)
