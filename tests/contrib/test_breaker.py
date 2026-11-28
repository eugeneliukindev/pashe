"""The CircuitBreaker of a Redis backend: it opens after failures in a row, skips Redis, and closes once Redis answers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Never, override

import pytest
import redis.asyncio
from redis import Redis
from redis.exceptions import ResponseError

from pashe import Cache
from pashe.backends import CircuitBreaker
from pashe.contrib.redis import AsyncRedisBackend, RedisBackend
from pashe.errors import BackendError, CircuitOpenError, InvalidOptionsError, WrongTypeError
from pashe.hooks import Circuit, Hook, LoggingHook
from tests.harness.helpers import Clock, RecordingHook, Source, cached_function

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from pashe.hooks import Failure


class _Circuits(Hook):
    """A hook that keeps what a breaker tells it."""

    def __init__(self) -> None:
        self.circuits: list[Circuit] = []

    @override
    def on_circuit(self, circuit: Circuit, /) -> None:
        self.circuits.append(circuit)


@pytest.fixture
def client(redis_url: str) -> Iterator[Redis]:
    client = Redis.from_url(redis_url, socket_timeout=1)
    yield client
    client.close()


def _down(
    monkeypatch: pytest.MonkeyPatch,
    client: Redis,
    error: Exception,
) -> list[str]:
    """Make every GET of client fail with error; return the GETs that reached it."""
    reached: list[str] = []

    def get(key: str) -> Never:
        reached.append(key)
        raise error

    monkeypatch.setattr(client, "get", get)
    return reached


def test_failures_in_a_row_open_it_and_then_no_call_reaches_redis(
    client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    told = _Circuits()
    backend = RedisBackend(
        client, breaker=CircuitBreaker(failure_threshold=3, open_for=10, hooks=[told], clock=Clock())
    )
    reached = _down(monkeypatch, client, redis.ConnectionError("down"))
    for _ in range(3):
        with pytest.raises(BackendError):
            backend.get("k")

    with pytest.raises(CircuitOpenError):
        backend.get("k")

    assert len(reached) == 3
    assert told.circuits == [Circuit(open=True, failures=3)]


def test_a_call_after_open_for_tries_redis_and_closes_it_if_redis_answers(
    client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock, told = Clock(), _Circuits()
    backend = RedisBackend(client, breaker=CircuitBreaker(failure_threshold=1, open_for=10, hooks=[told], clock=clock))
    _down(monkeypatch, client, redis.ConnectionError("down"))
    with pytest.raises(BackendError):
        backend.get("k")
    monkeypatch.undo()  # Redis is up again
    clock.now += 10

    backend.get("k")

    assert told.circuits == [Circuit(open=True, failures=1), Circuit(open=False, failures=0)]
    backend.get("k")


def test_a_try_that_fails_opens_it_again(client: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    backend = RedisBackend(client, breaker=CircuitBreaker(failure_threshold=1, open_for=10, clock=clock))
    reached = _down(monkeypatch, client, redis.ConnectionError("down"))
    with pytest.raises(BackendError):
        backend.get("k")
    clock.now += 10
    with pytest.raises(BackendError):
        backend.get("k")

    with pytest.raises(CircuitOpenError):
        backend.get("k")

    assert len(reached) == 2


def test_an_error_redis_answers_tells_it_is_up(client: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = RedisBackend(client, breaker=CircuitBreaker(failure_threshold=1, open_for=10, clock=Clock()))
    reached = _down(monkeypatch, client, ResponseError("WRONGTYPE Operation against a key holding the wrong kind"))

    for _ in range(3):
        with pytest.raises(WrongTypeError):
            backend.get("k")

    assert len(reached) == 3


def test_a_cached_call_answers_from_the_source_while_it_is_open(client: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    failures: list[Failure] = []
    backend = RedisBackend(client, breaker=CircuitBreaker(failure_threshold=1, open_for=10, clock=Clock()))
    cache = Cache(backend, hooks=[RecordingHook(failures=failures)])
    source = Source()
    get_user = cached_function(cache, source, ttl=60)
    _down(monkeypatch, client, redis.ConnectionError("down"))
    get_user(1)

    user = get_user(1)

    assert user == {"id": 1, "version": 1}
    assert isinstance(failures[-1].error, CircuitOpenError)


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: CircuitBreaker(failure_threshold=0), "CircuitBreaker.failure_threshold is 0"),
        (lambda: CircuitBreaker(open_for=0), "CircuitBreaker.open_for is 0"),
    ],
)
def test_options_that_cannot_work_are_refused(make: Callable[[], object], message: str) -> None:
    with pytest.raises(InvalidOptionsError, match=message):
        make()


async def test_an_async_backend_skips_redis_once_it_is_open(redis_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    client = redis.asyncio.Redis.from_url(redis_url, socket_timeout=1)
    backend = AsyncRedisBackend(client, breaker=CircuitBreaker(failure_threshold=1, open_for=10, clock=Clock()))

    async def get(_key: str) -> Never:
        msg = "down"
        raise redis.ConnectionError(msg)

    monkeypatch.setattr(client, "get", get)
    with pytest.raises(BackendError):
        await backend.get("k")

    with pytest.raises(CircuitOpenError):
        await backend.get("k")
    await client.aclose()


def test_the_logging_hook_logs_when_it_opens_and_closes(caplog: pytest.LogCaptureFixture) -> None:
    hook = LoggingHook()

    with caplog.at_level(logging.INFO, logger="pashe"):
        hook.on_circuit(Circuit(open=True, failures=5))
        hook.on_circuit(Circuit(open=False, failures=0))

    assert [record.levelno for record in caplog.records] == [logging.WARNING, logging.INFO]
    assert "5 times in a row" in caplog.records[0].getMessage()


def test_a_breaker_knows_no_backend_only_how_calls_ended() -> None:
    clock, told = Clock(), _Circuits()
    breaker = CircuitBreaker(failure_threshold=2, open_for=10, hooks=[told], clock=clock)
    breaker.on_failure()
    breaker.on_success()  # an answer between them: not in a row
    breaker.on_failure()
    breaker.on_failure()

    with pytest.raises(CircuitOpenError):
        breaker.before_call()

    clock.now += 10
    breaker.before_call()
    with pytest.raises(CircuitOpenError):
        breaker.before_call()  # a second call waits for the try
    assert told.circuits == [Circuit(open=True, failures=2)]


def _probing(clock: Clock) -> CircuitBreaker:
    """Return a breaker that one failure opened, open_for passed, so the next call is its probe."""
    breaker = CircuitBreaker(failure_threshold=1, open_for=10, clock=clock)
    down = BackendError("down")
    with pytest.raises(BackendError), breaker.guarding():
        raise down
    clock.now += 10
    return breaker


def test_a_probe_answered_with_an_error_of_the_server_closes_it(clock: Clock) -> None:
    breaker = _probing(clock)

    answered = WrongTypeError("not an integer")
    with pytest.raises(WrongTypeError), breaker.guarding():
        raise answered

    breaker.before_call()


def test_a_cancelled_probe_lets_the_next_call_try_the_backend(clock: Clock) -> None:
    breaker = _probing(clock)

    with pytest.raises(KeyboardInterrupt), breaker.guarding():
        raise KeyboardInterrupt

    with breaker.guarding():
        pass
    breaker.before_call()
