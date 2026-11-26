from __future__ import annotations

import contextlib
import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, final, override

from pashe._internal.checks import FUNCTION, expect_type, parse_int, parse_seconds
from pashe._internal.hooks import AllHooks
from pashe.errors import BackendError, CircuitOpenError
from pashe.hooks import Circuit, Hook

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pashe.options import Duration


class Breaker(ABC):
    """Decides whether a call may reach a backend, from how the backend answered the calls before it.

    A backend given one calls before_call before every call to its server, then on_success or
    on_failure, or on_cancel when the call ended before the server told anything. A failure is a
    BackendError, which every backend raises for a server it cannot reach; an error the server
    answered, such as WrongTypeError, tells it is up.

    Examples:
        A breaker of your own implements the four:

        >>> from pashe.backends import Breaker
        >>> class Never(Breaker):
        ...     def before_call(self):
        ...         pass
        ...
        ...     def on_success(self):
        ...         pass
        ...
        ...     def on_failure(self):
        ...         pass
        ...
        ...     def on_cancel(self):
        ...         pass
    """

    __slots__ = ()

    @abstractmethod
    def before_call(self) -> None:
        """Let a call reach the backend, or refuse it.

        Raises:
            CircuitOpenError: the call must skip the backend.
        """
        raise NotImplementedError

    @abstractmethod
    def on_success(self) -> None:
        """Take that the backend answered the call, with a result or an error of its own."""
        raise NotImplementedError

    @abstractmethod
    def on_failure(self) -> None:
        """Take that the backend could not be reached, as a BackendError tells."""
        raise NotImplementedError

    @abstractmethod
    def on_cancel(self) -> None:
        """Take that the call ended before the backend told anything, such as a cancelled task."""
        raise NotImplementedError

    @contextlib.contextmanager
    def guarding(self) -> Generator[None]:
        """Run a call to the server of a backend in the block: before_call first, then on_success or on_failure.

        Put it over the translation of the errors of the client, so the block raises the errors
        of pashe; an async call awaits in the block as a sync one does.

        Raises:
            CircuitOpenError: the call must skip the backend, from before_call.

        Examples:
            >>> from pashe.backends import CircuitBreaker
            >>> breaker = CircuitBreaker()
            >>> with breaker.guarding():
            ...     pass  # the call to the server
        """
        self.before_call()
        try:
            yield
        except BackendError:
            self.on_failure()
            raise
        except Exception:
            self.on_success()  # an error the server answered, such as WrongTypeError, tells it is up too
            raise
        except BaseException:
            self.on_cancel()  # such as a cancelled task: the server told nothing
            raise
        self.on_success()


@final
class CircuitBreaker(Breaker):
    """Skips a backend for a while after it failed several times in a row, instead of waiting on it for every call.

    While the server of a backend is down, every call waits for the timeout of its connection
    before the cache answers from the fallback or the source. Once failures calls in a row
    failed, the breaker opens: every call raises CircuitOpenError at once, a BackendError, which
    the cache handles as any failure of its backend. After open_for seconds one call tries the
    backend: it closes the breaker if the backend answers, and opens it again if not. Give one
    breaker to the backend and the bus over the same server, so both skip it together.

    Examples:
        >>> from redis import Redis
        >>> from pashe.backends import CircuitBreaker
        >>> from pashe.contrib.redis import RedisBackend
        >>> backend = RedisBackend(Redis(socket_timeout=1), breaker=CircuitBreaker(failure_threshold=5, open_for=10))
    """

    __slots__ = (
        "_clock",
        "_consecutive_failures",
        "_failure_threshold",
        "_half_open",
        "_hooks",
        "_lock",
        "_open_for",
        "_opened_at",
    )

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        open_for: Duration = 10,
        hooks: list[Hook] | tuple[Hook, ...] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a closed breaker.

        Args:
            failure_threshold: the failures in a row that open it.
            open_for: how long it skips the backend once open: seconds or a timedelta.
            hooks: what it tells when it opens and closes, through on_circuit.
            clock: monotonic seconds, for tests.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: failure_threshold is not 1 or more, or open_for is not positive.
        """
        self._failure_threshold = parse_int(
            "CircuitBreaker.failure_threshold",
            failure_threshold,
            low=1,
            meaning="the failures in a row that open it, 1 or more",
        )
        self._open_for = parse_seconds(
            "CircuitBreaker.open_for", open_for, "how long it skips the backend", positive=True
        )

        expect_type("clock", clock, FUNCTION)

        self._hooks = AllHooks(hooks)
        self._clock = clock

        self._lock = threading.Lock()  # the calls of threads and of tasks change it at once
        self._consecutive_failures = 0
        self._opened_at: float | None = None  # None while closed
        self._half_open = False  # one call tries the backend once open_for passed

    @override
    def before_call(self) -> None:
        with self._lock:
            if self._opened_at is None:
                return
            if self._clock() - self._opened_at < self._open_for or self._half_open:
                raise CircuitOpenError(self._consecutive_failures)
            self._half_open = True

    @override
    def on_success(self) -> None:
        with self._lock:
            closes = self._opened_at is not None
            self._consecutive_failures = 0
            self._opened_at = None
            self._half_open = False
        if closes:
            self._hooks.on_circuit(Circuit(open=False, failures=0))

    @override
    def on_cancel(self) -> None:
        with self._lock:
            self._half_open = False  # the next call tries the backend instead

    @override
    def on_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            opens = self._half_open or (
                self._opened_at is None and self._consecutive_failures >= self._failure_threshold
            )
            if opens:
                self._opened_at = self._clock()
                self._half_open = False
            consecutive_failures = self._consecutive_failures
        if opens:
            self._hooks.on_circuit(Circuit(open=True, failures=consecutive_failures))


@final
class NoOpBreaker(Breaker):
    """Lets every call reach the backend: what a backend has unless it is given another breaker."""

    __slots__ = ()

    @override
    def before_call(self) -> None:
        """Let the call through."""

    @override
    def on_success(self) -> None:
        """Count nothing."""

    @override
    def on_failure(self) -> None:
        """Count nothing."""

    @override
    def on_cancel(self) -> None:
        """Count nothing."""
