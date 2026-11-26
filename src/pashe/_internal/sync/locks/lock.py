from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Self, final

from pashe._internal.locks.lock import BaseLock
from pashe._internal.sync.locks.locking import take
from pashe.errors import BackendError, LockLostError, LockTimeoutError

if TYPE_CHECKING:
    from types import TracebackType

    from pashe._internal.sync.backends.prefixed import PrefixedBackend
    from pashe._internal.sync.locks.locking import Lease
    from pashe.hooks import Hook


@final
class Lock(BaseLock):
    """A lock for a ``with`` block, held in the backend for every process over it.

    Locks.lock and Locks.try_lock make it. Entering the block waits for the lock, unless
    try_lock already took it. While the block runs, a thread extends the lock by ttl every third
    of ttl, so the block may run longer than ttl; the lock is released after the block. A sync
    block cannot be interrupted: if an extension fails, the block runs to its end and
    LockLostError is raised after it, unless the block raised an error of its own.

    Examples:
        >>> from pashe import Locks
        >>> from pashe.backends import MemoryBackend
        >>> locks = Locks(MemoryBackend())
        >>> with locks.lock("report", ttl=30) as lock:
        ...     lock.key
        'report'
    """

    __slots__ = ("_backend", "_extender", "_lease", "_stop")

    def __init__(
        self,
        backend: PrefixedBackend,
        *,
        key: str,
        ttl: float,
        timeout: float | None = None,
        holders: int = 1,
        lease: Lease | None = None,
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

        if self._lease is None:
            self._lease = take(
                self._backend, self._slots, self._ttl, timeout=self._timeout, name=self._key, hooks=self._hooks
            )
            if self._lease is None:
                raise LockTimeoutError(self._key, self._timeout)

        self._lost = None

        self._stop = threading.Event()  # the last block set the one before, and a lock may be entered again
        self._extender = threading.Thread(
            target=self._keep_extending, args=(self._lease,), name=f"pashe-lock-{self._key}", daemon=True
        )
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
        if self._lease is None:
            return
        self._lease.release()
        self._lease = None

    def _keep_extending(self, lease: Lease) -> None:
        while not self._stop.wait(self._extend_interval):
            try:
                extended = lease.extend(self._ttl)
            except BackendError as error:
                self._lost = error
                return
            if not extended:
                self._lost = LockLostError(self._key, expired=True)
                return
