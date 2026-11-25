from __future__ import annotations

import contextlib
import contextvars
import threading
from concurrent import futures
from typing import TYPE_CHECKING, Any, Final, Literal, final

from pashe._internal.checks import is_async
from pashe.errors import OverloadedError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Hashable

_THREAD_PREFIX: Final = "pashe"


@final
class SingleFlight:
    __slots__ = ("_calls", "_lock")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[Hashable, _Shared[Any]] = {}

    def share[T](self, key: Hashable, run: Callable[[], T]) -> T:
        with self._lock:
            call: _Shared[T] | None = self._calls.get(key)
            leading = call is None
            if call is None:
                call = _Shared()
                self._calls[key] = call
        if not leading:
            return call.wait()  # what run returned; raises what it raised
        try:
            call.value = run()
        except BaseException as error:
            call.error = error
            raise
        else:
            return call.value
        finally:
            with self._lock:
                self._calls.pop(key)
            call.done.release()


@final
class _Shared[T]:
    # the load of a leader its waiters take: lighter than a Future, which makes a Condition per call
    __slots__ = ("done", "error", "value")

    value: T  # set by the leader before it releases done, unless it raised

    def __init__(self) -> None:
        self.done = threading.Lock()
        self.done.acquire()  # held until the leader finished
        self.error: BaseException | None = None

    def wait(self) -> T:
        self.done.acquire()  # once the leader released it
        self.done.release()  # for the other waiters
        if self.error is not None:
            raise self.error
        return self.value


@final
class ConcurrencyLimit:
    __slots__ = ("_held", "_semaphore")

    def __init__(self, limit: int) -> None:
        self._semaphore = threading.BoundedSemaphore(limit) if limit > 0 else None
        # whether the thread loads in a slot already: a function that calls itself waits for no second one
        self._held = contextvars.ContextVar(f"pashe_slot_{id(self)}", default=False)

    @contextlib.contextmanager
    def slot(self, *, has_stale_answer: bool) -> Generator[None]:
        if self._semaphore is None or self._held.get():
            yield
            return
        if not self._semaphore.acquire(blocking=not has_stale_answer):  # a call a stale result answers waits for none
            raise OverloadedError
        token = self._held.set(True)
        try:
            yield
        finally:
            self._held.reset(token)
            self._semaphore.release()


@final
class BackgroundTasks:
    __slots__ = ("_executor", "_lock", "_stopped")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._executor: futures.ThreadPoolExecutor | None = None
        self._stopped = False

    def add_task[**P, T](self, work: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> futures.Future[T] | None:
        with self._lock:
            if self._stopped:
                return None
            if self._executor is None:
                self._executor = futures.ThreadPoolExecutor(thread_name_prefix=_THREAD_PREFIX)
            return self._executor.submit(work, *args, **kwargs)

    def close(self) -> None:
        with self._lock:
            self._stopped = True
            executor = self._executor
        if executor is not None:
            executor.shutdown(wait=True)


def check_side(function: Callable[..., object], action: Literal["decorate", "cache"]) -> None:
    if is_async(function):
        msg = f"{getattr(function, '__qualname__', function)} is async: {action} it with an AsyncCache"
        raise TypeError(msg)


def shield[T](value: T) -> T:
    return value
