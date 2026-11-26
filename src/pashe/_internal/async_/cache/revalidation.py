from __future__ import annotations

import asyncio
import functools
from dataclasses import replace
from typing import TYPE_CHECKING, Final, final

from pashe._internal.async_.locks.locking import arelease, atry_acquire
from pashe._internal.cache.keys import KeyPrefix
from pashe.errors import BackendError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.tasks import AsyncBackgroundTasks
    from pashe._internal.cache.call import Answer, CallState
    from pashe.hooks import Hook

# Bounds the revalidation lock and the load holding it, so a load that hangs or a revalidator that
# dies blocks revalidations for at most this long.
_LOCK_SECONDS: Final = 60.0

type AsyncLoadAndStore = Callable[[CallState], Awaitable[Answer]]  # loads the entry of a call and stores it
type _Lock = tuple[str, bytes | None]


@final
class AsyncRevalidation:
    # The loads of an entry that run apart from the call it answers: one per key across processes,
    # under a lock in the backend, in the background tasks of the cache.
    __slots__ = ("_backend", "_background", "_hooks", "_slow_after")

    def __init__(
        self,
        *,
        backend: AsyncPrefixedBackend,
        background: AsyncBackgroundTasks,
        hooks: Hook,
        slow_after: float,
    ) -> None:
        self._backend = backend
        self._background = background
        self._hooks = hooks
        self._slow_after = slow_after  # Stale.slow_after, in seconds

    async def start(self, state: CallState, load_and_store: AsyncLoadAndStore) -> None:
        # Revalidate in the background, unless another call does already; the call answers at once.
        lock_key = KeyPrefix.REVALIDATION_LOCK + state.key
        try:  # held as long as a load in the background may take, not the window: a slow load still stores
            owner = await atry_acquire(self._backend, lock_key, _LOCK_SECONDS)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.REVALIDATION_LOCK, state.key, error))
            return
        if owner is None:
            return

        # the old result answered, so a full limit of loads skips this one
        background = replace(state, load_seconds=0, has_stale_answer=True)
        task = self._background.add_task(
            self._load, background, load_and_store, lock=(lock_key, owner), within=_LOCK_SECONDS
        )
        if task is None:
            await arelease(self._backend, lock_key, owner, hooks=self._hooks)  # the cache is closing

    async def wait_at_most_slow_after(self, state: CallState, load_and_store: AsyncLoadAndStore) -> Answer | None:
        # The load, if it ends within Stale.slow_after; None when it is slower or another call
        # revalidates already, and the stale result answers. A slower load goes on in the background.
        lock_key = KeyPrefix.REVALIDATION_LOCK + state.key
        lock: _Lock
        try:
            owner = await atry_acquire(self._backend, lock_key, _LOCK_SECONDS)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.REVALIDATION_LOCK, state.key, error))
            lock = (lock_key, None)  # load all the same, with no lock to release
        else:
            if owner is None:
                return None
            lock = (lock_key, owner)

        answered = asyncio.Event()  # the caller stopped waiting: a failure of the load goes to on_error
        task = self._background.add_task(
            self._load,
            replace(state, load_seconds=0),
            load_and_store,
            lock=lock,
            within=_LOCK_SECONDS,
            answered=answered,
        )

        if task is None:  # the cache is closing: no background work, wait for the load
            return await self._load(state, load_and_store, lock=lock, within=None, answered=answered)

        try:  # the load goes on either way; the call waits for it at most Stale.slow_after
            await asyncio.wait({task}, timeout=self._slow_after)
        finally:
            if not task.done():
                answered.set()

        if answered.is_set():
            # a load that fails as the caller stops waiting may raise into the task: nobody reads it there
            task.add_done_callback(functools.partial(self._report_unread, state.key))
            return None

        loaded = task.result()
        if loaded is not None:
            state.load_seconds += loaded.load_seconds  # the call waited for it
        return loaded

    async def _load(
        self,
        state: CallState,
        load_and_store: AsyncLoadAndStore,
        *,
        lock: _Lock,
        within: float | None,
        answered: asyncio.Event | None = None,
    ) -> Answer | None:
        try:
            # A background load must not outlive its lock; a thread cannot be interrupted, so the sync side waits.
            async with asyncio.timeout(within):
                return await load_and_store(state)
        except Exception as error:
            if answered is not None and not answered.is_set():
                raise
            self._hooks.on_error(Failure(Operation.REVALIDATION, state.key, error))
            return None
        finally:
            await arelease(self._backend, *lock, hooks=self._hooks)

    def _report_unread(self, key: str, task: asyncio.Task[Answer | None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if isinstance(error, Exception):
            self._hooks.on_error(Failure(Operation.REVALIDATION, key, error))
