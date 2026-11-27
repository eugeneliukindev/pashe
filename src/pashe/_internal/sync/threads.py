from __future__ import annotations

import contextlib
import contextvars
import threading
from concurrent import futures
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, final

from pashe._internal.checks import is_async
from pashe.errors import OverloadedError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Hashable

_THREAD_PREFIX: Final = "pashe"


class Decorator(Protocol):
    """A decorator of a ``def`` function that keeps its signature, as locked, limited and invalidates return."""

    def __call__[**P, R](self, function: Callable[P, R], /) -> Callable[P, R]:
        """Return function, run as the decorator says."""
        ...


@final
class SharedLoads:
    __slots__ = ("_loads", "_lock")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loads: dict[Hashable, _SharedLoad[Any]] = {}

    def share[T](self, key: Hashable, run: Callable[[], T]) -> T:
        with self._lock:
            load: _SharedLoad[T] | None = self._loads.get(key)
            leading = load is None
            if load is None:
                load = _SharedLoad()
                self._loads[key] = load
        if not leading:
            return load.wait()  # what run returned; raises what it raised
        try:
            load.result = run()
        except BaseException as error:
            load.error = error
            raise
        else:
            return load.result
        finally:
            with self._lock:
                self._loads.pop(key)
            load.done.release()


@final
class LoadLimit:
    __slots__ = ("_held", "_semaphore")

    def __init__(self, limit: int) -> None:
        self._semaphore = threading.BoundedSemaphore(limit) if limit > 0 else None
        # whether the thread loads in a slot already: a function that calls itself waits for no second one
        self._held = contextvars.ContextVar(f"pashe_slot_{id(self)}", default=False)

    @contextlib.contextmanager
    def slot(self, *, wait: bool) -> Generator[None]:
        """A slot of the limit to load in.

        With no limit, or inside a load of the same slots, it does nothing; with every slot
        taken, it waits, or raises OverloadedError if not wait.
        """
        if self._semaphore is None or self._held.get():
            yield
            return
        if not self._semaphore.acquire(blocking=wait):
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

    def add_task[**P, T](
        self,
        work: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> futures.Future[T] | None:
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


@final
class _SharedLoad[T]:
    # the load of a leader its waiters take: lighter than a Future, which makes a Condition per load
    __slots__ = ("done", "error", "result")

    result: T  # set by the leader before it releases done, unless it raised

    def __init__(self) -> None:
        self.done = threading.Lock()
        self.done.acquire()  # held until the leader finished
        self.error: BaseException | None = None

    def wait(self) -> T:
        self.done.acquire()  # once the leader released it
        self.done.release()  # for the other waiters
        if self.error is not None:
            raise self.error
        return self.result


def validate_sync(
    function: Callable[..., object],
    action: Literal["decorate", "cache"],
    owner: object,
) -> None:
    """``owner``: the cache, the locks or the limiter whose decorator takes function; the error names its async twin."""
    if is_async(function):
        twin = f"Async{type(owner).__name__}"
        msg = f"{getattr(function, '__qualname__', function)} is async: {action} it with {twin}"
        raise TypeError(msg)


def shield[T](value: T) -> T:
    return value
