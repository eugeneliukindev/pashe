from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self, final

from pashe._internal.async_.locks.locking import atake
from pashe._internal.locks.lock import BaseLock
from pashe.errors import BackendError, LockLostError, LockTimeoutError

if TYPE_CHECKING:
    from types import TracebackType

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.locks.locking import AsyncLease
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

    __slots__ = ("_backend", "_cancelled", "_exiting", "_extender", "_lease", "_task")

    def __init__(
        self,
        backend: AsyncPrefixedBackend,
        *,
        key: str,
        ttl: float,
        timeout: float | None = None,
        holders: int = 1,
        lease: AsyncLease | None = None,
        hooks: Hook,
    ) -> None:
        """Made by the lock methods of a cache, not by hand.

        Args:
            backend: the backend of the cache, seen through its prefix.
            key: the name of the lock.
            ttl: how long the lock lives without an extension, in seconds, more than 0.
            timeout: the most entering waits, in seconds, 0 or more; None waits as long as it takes.
            holders: how many may hold the lock at once, 1 or more.
            lease: the place try_lock already took; None takes one on entering.
            hooks: the hooks of the cache: a failed release of the lock goes to their on_error.
        """
        super().__init__(key=key, ttl=ttl, timeout=timeout, holders=holders, hooks=hooks)

        self._backend = backend
        self._lease = lease

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

        if self._lease is None:
            self._lease = await atake(
                self._backend, self._slots, self._ttl, timeout=self._timeout, name=self._key, hooks=self._hooks
            )
            if self._lease is None:
                raise LockTimeoutError(self._key, self._timeout)

        self._lost = None  # what the last block left, as a lock may be entered again
        self._cancelled = False
        self._exiting = False

        self._task = asyncio.current_task()
        self._extender = asyncio.create_task(self._keep_extending(self._lease))
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
        if self._lease is None:
            return
        await self._lease.release()
        self._lease = None

    async def _keep_extending(self, lease: AsyncLease) -> None:
        while True:
            await asyncio.sleep(self._extend_interval)
            try:
                extended = await lease.extend(self._ttl)
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
