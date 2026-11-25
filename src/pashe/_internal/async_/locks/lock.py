from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self, final

from pashe._internal.async_.locks.locking import aacquire
from pashe._internal.locks.lock import BaseLock
from pashe.errors import BackendError, LockLostError, LockTimeoutError

if TYPE_CHECKING:
    from types import TracebackType

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe.hooks import Hook


@final
class AsyncLock(BaseLock):
    """Lock for ``async with``: if an extension fails, the block is cancelled.

    AsyncCache.lock and AsyncCache.try_lock make it. LockLostError is then raised in place of
    the cancellation, unless the block raised an error of its own.

    Examples:
        >>> import asyncio
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> async def build_report() -> str:
        ...     cache = AsyncCache(AsyncMemoryBackend())
        ...     async with cache.lock("report", ttl=30) as lock:
        ...         return lock.key
        >>> asyncio.run(build_report())
        'report'
    """

    __slots__ = ("_backend", "_cancelled", "_exiting", "_extender", "_task")

    def __init__(
        self,
        backend: AsyncPrefixedBackend,
        hooks: Hook,
        *,
        key: str,
        ttl: float,
        timeout: float | None = None,
        owner: bytes | None = None,
    ) -> None:
        """Made by the lock methods of a cache, not by hand.

        Args:
            backend: the backend of the cache, seen through its prefix.
            hooks: the hooks of the cache: a failed release of the lock goes to their on_error.
            key: the name of the lock.
            ttl: how long the lock lives without an extension, in seconds, more than 0.
            timeout: the most entering waits, in seconds, 0 or more; None waits as long as it takes.
            owner: the owner token of a lock try_lock already took; None takes it on entering.
        """
        super().__init__(hooks, key=key, ttl=ttl, timeout=timeout, owner=owner)

        self._backend = backend

        self._task: asyncio.Task[object] | None = None
        self._extender: asyncio.Task[None] | None = None
        self._cancelled = False  # the extender cancelled the block
        self._exiting = False

    async def __aenter__(self) -> Self:
        """Take the lock, waiting while someone else holds it, and start extending it.

        Returns:
            The lock.

        Raises:
            LockTimeoutError: the lock stayed busy for the whole timeout.
            RuntimeError: the lock is entered inside its own block: the inner exit would release it.
        """
        if self._extender is not None and not self._extender.done():
            msg = f"the lock {self._key!r} is entered inside its own block; take another lock object"
            raise RuntimeError(msg)

        if self._owner is None:
            owner = await aacquire(self._backend, self._key, self._ttl, timeout=self._timeout)
            if owner is None:
                raise LockTimeoutError(self._key, self._timeout)
            self._owner = owner

        self._lost = None  # what the last block left, as a lock may be entered again
        self._cancelled = False
        self._exiting = False

        self._task = asyncio.current_task()
        self._extender = asyncio.create_task(self._keep_extending())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop extending and release the lock, also when the block was cancelled.

        Args:
            exc_type: the type of the error the block raised, if it did.
            exc: the error the block raised, if it did.
            traceback: the traceback of that error.

        Raises:
            LockLostError: the lock was lost while the block ran, and the block raised nothing
                but the cancellation of the lost lock.
        """
        self._exiting = True  # from now on the extender must not cancel this task
        try:
            if self._extender is not None:
                self._extender.cancel()
                await asyncio.wait({self._extender})  # unlike await, never raises the extender's cancel
        finally:  # a task cancelled here, or in the block, still releases the lock
            await asyncio.shield(self._release())
        if self._lost is None:
            return
        if self._cancelled and self._task is not None and self._task.uncancel() > 0:
            return  # someone else cancelled the task too: their cancellation goes on
        if exc is None or isinstance(exc, asyncio.CancelledError):
            raise LockLostError(self._key) from self._lost

    async def _release(self) -> None:
        if self._owner is None:
            return
        try:
            await self._backend.delete_if_equals(self._key, self._owner)
        except BackendError as error:
            self._report_release_error(error)
        self._owner = None

    async def _keep_extending(self) -> None:
        while self._owner is not None:
            await asyncio.sleep(self._extend_interval)
            try:
                extended = await self._backend.expire_if_equals(self._key, self._owner, self._ttl)
            except BackendError as error:
                self._lose(error)
                return
            if not extended:
                self._lose(LockLostError(self._key, expired=True))
                return

    def _lose(self, error: BackendError | LockLostError) -> None:
        self._lost = error
        if self._task is not None and not self._exiting:
            self._cancelled = True
            self._task.cancel()  # stop the block: someone else may hold the lock now
