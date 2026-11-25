from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Self, final

from pashe._internal.locks.lock import BaseLock
from pashe._internal.sync.locks.locking import acquire
from pashe.errors import BackendError, LockLostError, LockTimeoutError

if TYPE_CHECKING:
    from types import TracebackType

    from pashe._internal.sync.backends.prefixed import PrefixedBackend
    from pashe.hooks import Hook


@final
class Lock(BaseLock):
    """A lock for a ``with`` block, held in the backend for every cache over it.

    Cache.lock and Cache.try_lock make it. Entering the block waits for the lock, unless
    try_lock already took it. While the block runs, a thread extends the lock by ttl every third
    of ttl, so the block may run longer than ttl; the lock is released after the block. A sync
    block cannot be interrupted: if an extension fails, the block runs to its end and
    LockLostError is raised after it, unless the block raised an error of its own.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> cache = Cache(MemoryBackend())
        >>> with cache.lock("report", ttl=30) as lock:
        ...     lock.key
        'report'
    """

    __slots__ = ("_backend", "_extender", "_stop")

    def __init__(
        self,
        backend: PrefixedBackend,
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

        self._stop = threading.Event()
        self._extender: threading.Thread | None = None

    def __enter__(self) -> Self:
        """Take the lock, waiting while someone else holds it, and start extending it.

        Returns:
            The lock.

        Raises:
            LockTimeoutError: the lock stayed busy for the whole timeout.
            RuntimeError: the lock is entered inside its own block: the inner exit would release it.
        """
        if self._extender is not None and self._extender.is_alive():
            msg = f"the lock {self._key!r} is entered inside its own block; take another lock object"
            raise RuntimeError(msg)

        if self._owner is None:
            owner = acquire(self._backend, self._key, self._ttl, timeout=self._timeout)
            if owner is None:
                raise LockTimeoutError(self._key, self._timeout)
            self._owner = owner

        self._lost = None

        self._stop = threading.Event()  # the last block set the one before, and a lock may be entered again
        self._extender = threading.Thread(target=self._keep_extending, name=f"pashe-lock-{self._key}", daemon=True)
        self._extender.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop extending and release the lock.

        Args:
            exc_type: the type of the error the block raised, if it did.
            exc: the error the block raised, if it did.
            traceback: the traceback of that error.

        Raises:
            LockLostError: the lock was lost while the block ran, and the block raised nothing.
        """
        self._stop.set()
        try:
            if self._extender is not None:
                self._extender.join()
        finally:  # an interrupt while it waits still releases the lock
            self._release()
        if self._lost is not None and exc is None:
            raise LockLostError(self._key) from self._lost

    def _release(self) -> None:
        if self._owner is None:
            return
        try:
            self._backend.delete_if_equals(self._key, self._owner)
        except BackendError as error:
            self._report_release_error(error)
        self._owner = None

    def _keep_extending(self) -> None:
        while not self._stop.wait(self._extend_interval):
            if self._owner is None:
                return
            try:
                extended = self._backend.expire_if_equals(self._key, self._owner, self._ttl)
            except BackendError as error:
                self._lost = error
                return
            if not extended:
                self._lost = LockLostError(self._key, expired=True)
                return
