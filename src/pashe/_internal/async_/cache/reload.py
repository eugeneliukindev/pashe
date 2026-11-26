from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Final, final

from pashe.errors import BackendError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pashe._internal.async_.locks.locking import AsyncLease, AsyncLoadLocks
    from pashe._internal.async_.tasks import AsyncBackgroundTasks
    from pashe._internal.cache.call import Answer, Call
    from pashe.hooks import Hook

# Bounds the revalidation lock and the load holding it, so a load that hangs or a revalidator that
# dies blocks revalidations for at most this long.
_LOCK_SECONDS: Final = 60.0

type AsyncLoadAndStore = Callable[[Call], Awaitable[Answer]]  # loads the entry of a call and stores it


@final
class AsyncReload:
    # The loads of an entry that run apart from the call it answers: one per key across processes,
    # under a lock in the backend, in the background tasks of the cache.
    __slots__ = ("_background", "_hooks", "_load_locks", "_slow_after")

    def __init__(
        self,
        *,
        load_locks: AsyncLoadLocks,
        background: AsyncBackgroundTasks,
        slow_after: float,
        hooks: Hook,
    ) -> None:
        self._load_locks = load_locks
        self._background = background
        self._slow_after = slow_after  # Stale.slow_after, in seconds
        self._hooks = hooks

    async def start(self, call: Call, load_and_store: AsyncLoadAndStore) -> None:
        # Revalidate in the background, unless another call does already; the call answers at once.
        try:  # held as long as a load in the background may take, not the window: a slow load still stores
            lease = await self._load_locks.try_take_reload(call.key, _LOCK_SECONDS)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.REVALIDATION_LOCK, call.key, error))
            return
        if lease is None:
            return

        task = self._background.add_task(
            self._load, call.restarted(), load_and_store, lease=lease, within=_LOCK_SECONDS
        )
        if task is None:
            await lease.release()  # the cache is closing

    async def wait_at_most_slow_after(self, call: Call, load_and_store: AsyncLoadAndStore) -> Answer | None:
        # The load, if it ends within Stale.slow_after; None when it is slower or another call
        # revalidates already, and the stale result answers. A slower load goes on in the background.
        lease: AsyncLease | None
        try:
            lease = await self._load_locks.try_take_reload(call.key, _LOCK_SECONDS)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.REVALIDATION_LOCK, call.key, error))
            lease = None  # load all the same, with no lock to release
        else:
            if lease is None:
                return None

        answered = asyncio.Event()  # the caller stopped waiting: a failure of the load goes to on_error
        task = self._background.add_task(
            self._load,
            call.restarted(),
            load_and_store,
            lease=lease,
            within=_LOCK_SECONDS,
            answered=answered,
        )

        if task is None:  # the cache is closing: no background work, wait for the load
            return await self._load(call, load_and_store, lease=lease, within=None, answered=answered)

        try:  # the load goes on either way; the call waits for it at most Stale.slow_after
            await asyncio.wait({task}, timeout=self._slow_after)
        finally:
            if not task.done():
                answered.set()

        if answered.is_set():
            # a load that fails as the caller stops waiting may raise into the task: nobody reads it there
            task.add_done_callback(functools.partial(self._report_unread, call.key))
            return None
        return task.result()

    async def _load(
        self,
        call: Call,
        load_and_store: AsyncLoadAndStore,
        *,
        lease: AsyncLease | None,
        within: float | None,
        answered: asyncio.Event | None = None,
    ) -> Answer | None:
        try:
            # A background load must not outlive its lock; a thread cannot be interrupted, so the sync side waits.
            async with asyncio.timeout(within):
                return await load_and_store(call)
        except Exception as error:
            if answered is not None and not answered.is_set():
                raise
            self._hooks.on_error(Failure(Operation.REVALIDATION, call.key, error))
            return None
        finally:
            if lease is not None:
                await lease.release()

    def _report_unread(self, key: str, task: asyncio.Task[Answer | None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if isinstance(error, Exception):
            self._hooks.on_error(Failure(Operation.REVALIDATION, key, error))
