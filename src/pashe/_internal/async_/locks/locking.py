from __future__ import annotations

import asyncio
import random
import secrets
import time
from typing import TYPE_CHECKING, Final, final

from pashe._internal.async_.tasks import ashield
from pashe._internal.cache.keys import KeyPrefix
from pashe.errors import BackendError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pashe._internal.async_.backends.backend import AsyncBackend
    from pashe.hooks import Hook

_OWNER_BYTES: Final = 16
_FIRST_PAUSE: Final = 0.01  # seconds before the first new check of a busy lock
_LONGEST_PAUSE: Final = 0.5
_PAUSES_PER_TTL: Final = 10  # a waiter checks at least this often within the ttl of the lock
_JITTER: Final = 0.5  # a pause is cut by up to this share, so waiters do not check together


@final
class AsyncLease:
    # A lock taken in the backend: only its holder, by the owner token, extends and releases it.
    __slots__ = ("_backend", "_hooks", "_name", "_owner", "_slot")

    def __init__(
        self,
        backend: AsyncBackend,
        slot: str,
        owner: bytes,
        *,
        name: str,
        hooks: Hook,
    ) -> None:
        self._backend = backend
        self._slot = slot  # the key in the backend of the place it holds
        self._owner = owner
        self._name = name  # what a failure of its release names
        self._hooks = hooks

    async def extend(self, ttl: float) -> bool:
        # False if the lock expired and may be someone else's now; a failing backend raises
        return await self._backend.expire_if_equals(self._slot, self._owner, ttl)

    async def release(self) -> None:
        # no caller waits for an error of a release: it goes to on_error
        try:
            await ashield(
                self._backend.delete_if_equals(self._slot, self._owner)
            )  # a cancelled caller still releases it
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.RELEASE_LOCK, self._name, error))


@final
class AsyncLoadLocks:
    # The locks a cache takes in its backend around its own loads, apart from the keys of results:
    # one load of a key at a time, as Stampede.lock_for asks, and one reload of a key at a time. A
    # failing backend raises: the caller loads all the same and tells its hooks.
    __slots__ = ("_backend", "_hooks")

    def __init__(self, backend: AsyncBackend, *, hooks: Hook) -> None:
        self._backend = backend
        self._hooks = hooks

    async def take_load(self, key: str, ttl: float) -> AsyncLease | None:
        # waits while another load of key holds it: None only for a timeout, which it has none of
        lock_key = KeyPrefix.STAMPEDE_LOCK + key
        return await atake(self._backend, (lock_key,), ttl, name=lock_key, hooks=self._hooks)

    async def try_take_reload(self, key: str, ttl: float) -> AsyncLease | None:
        # None while another reload of key holds it
        lock_key = KeyPrefix.REVALIDATION_LOCK + key
        return await atry_take(self._backend, (lock_key,), ttl, name=lock_key, hooks=self._hooks)


async def atake(
    backend: AsyncBackend,
    slots: Sequence[str],
    ttl: float,
    *,
    timeout: float | None = None,  # noqa: ASYNC109 - bounds the wait, not the block that holds the lock
    name: str,
    hooks: Hook,
) -> AsyncLease | None:
    # a place of the lock, waiting while each is taken; None after timeout
    backoff = _Backoff(ttl, timeout)
    lease = await atry_take(backend, slots, ttl, name=name, hooks=hooks)
    while lease is None:
        pause = backoff.next_pause()
        if pause is None:
            return None
        await asyncio.sleep(pause)
        lease = await atry_take(backend, slots, ttl, name=name, hooks=hooks)
    return lease


async def atry_take(
    backend: AsyncBackend,
    slots: Sequence[str],
    ttl: float,
    *,
    name: str,
    hooks: Hook,
) -> AsyncLease | None:
    # a place of the lock if one is free now
    first = random.randrange(len(slots))  # noqa: S311 - spreads the holders over the slots, not a secret
    for slot in (*slots[first:], *slots[:first]):
        owner = secrets.token_hex(_OWNER_BYTES).encode()
        if await backend.set_if_absent(slot, owner, ttl=ttl):  # noqa: WPS476 - the next place only if this one is taken
            return AsyncLease(backend, slot, owner, name=name, hooks=hooks)
    return None


@final
class _Backoff:
    __slots__ = ("_deadline", "_longest", "_pause")

    def __init__(self, ttl: float, timeout: float | None) -> None:
        self._pause = _FIRST_PAUSE
        self._longest = max(_FIRST_PAUSE, min(_LONGEST_PAUSE, ttl / _PAUSES_PER_TTL))
        self._deadline = None if timeout is None else time.monotonic() + timeout

    def next_pause(self) -> float | None:
        pause = self._pause * random.uniform(1 - _JITTER, 1)  # noqa: S311 - jitter, not a secret
        self._pause = min(self._pause * 2, self._longest)
        if self._deadline is None:
            return pause
        left = self._deadline - time.monotonic()
        return None if left <= 0 else min(pause, left)
