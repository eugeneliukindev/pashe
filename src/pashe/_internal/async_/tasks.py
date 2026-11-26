from __future__ import annotations

import asyncio
import contextlib
import contextvars
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, final

from pashe._internal.checks import is_async
from pashe.errors import OverloadedError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Hashable

ashield: Final = asyncio.shield  # a cancelled caller still releases what it holds


@final
class AsyncSharedLoads:
    __slots__ = ("_loads",)

    def __init__(self) -> None:
        self._loads: dict[Hashable, asyncio.Future[Any]] = {}

    async def share[T](self, key: Hashable, run: Callable[[], Awaitable[T]]) -> T:
        load = self._loads.get(key)
        while load is not None:
            try:
                shared: T = await asyncio.shield(load)  # a waiter that is cancelled leaves alone
            except _LeaderLeft:
                load = self._loads.get(key)
            else:
                return shared

        load = asyncio.get_running_loop().create_future()
        self._loads[key] = load
        try:
            result = await run()
        except asyncio.CancelledError:
            _fail(load, _LeaderLeft())
            raise
        except BaseException as error:
            _fail(load, error)
            raise
        finally:
            del self._loads[key]  # noqa: WPS420 - the waiters hold the future; pop would return one nobody awaits

        load.set_result(result)
        return result


@final
class AsyncLoadLimit:
    __slots__ = ("_held", "_semaphore")

    def __init__(self, limit: int) -> None:
        self._semaphore = asyncio.Semaphore(limit) if limit > 0 else None
        # whether the task loads in a slot already: a function that calls itself waits for no second one
        self._held = contextvars.ContextVar(f"pashe_slot_{id(self)}", default=False)

    def slot(self, *, wait: bool) -> contextlib.AbstractAsyncContextManager[object]:
        # with no limit, or inside a load of the same slots, a context that does nothing; with every
        # slot taken, one that waits, or OverloadedError if not wait
        if self._semaphore is None or self._held.get():
            return contextlib.nullcontext()
        if self._semaphore.locked() and not wait:
            raise OverloadedError
        return self._taken(self._semaphore)

    @contextlib.asynccontextmanager
    async def _taken(self, semaphore: asyncio.Semaphore) -> AsyncGenerator[None]:
        async with semaphore:
            token = self._held.set(True)
            try:
                yield
            finally:
                self._held.reset(token)


@final
class AsyncBackgroundTasks:
    __slots__ = ("_stopped", "_tasks")

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()
        self._stopped = False

    def add_task[**P, T](
        self,
        work: Callable[P, Coroutine[Any, Any, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> asyncio.Task[T] | None:
        if self._stopped:
            return None
        task = asyncio.create_task(work(*args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def aclose(self) -> None:
        self._stopped = True
        await asyncio.gather(*self._tasks, return_exceptions=True)


class AsyncDecorator(Protocol):
    """A decorator of an ``async def`` function that keeps its signature, as locked, limited and invalidates return."""

    def __call__[**P, R](self, function: Callable[P, Awaitable[R]], /) -> Callable[P, Awaitable[R]]:
        """Return function, run as the decorator says."""
        ...


def aexpect_side(
    function: Callable[..., object],
    action: Literal["decorate", "cache"],
    owner: object,
) -> None:
    # owner: the cache, the locks or the limiter whose decorator takes function; the error names its sync twin
    if not is_async(function):
        twin = type(owner).__name__.removeprefix("Async")
        msg = f"{getattr(function, '__qualname__', function)} is not async: {action} it with {twin}"
        raise TypeError(msg)


class _LeaderLeft(Exception):  # noqa: N818 - not an error: tells a waiter to load itself
    """The caller that loaded was cancelled: a caller that waited for it loads instead."""


def _fail(load: asyncio.Future[Any], error: BaseException) -> None:
    load.set_exception(error)
    load.exception()  # retrieved, so a shared load nobody waited for logs no "never retrieved"
