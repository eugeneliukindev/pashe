from __future__ import annotations

import functools
from typing import TYPE_CHECKING, final, override

from pashe._internal.async_.backends.backend import AsyncBackend
from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
from pashe._internal.async_.locks.lock import AsyncLock
from pashe._internal.async_.locks.locking import atry_take
from pashe._internal.async_.tasks import validate_async
from pashe._internal.cache.keys import CallKeys, KeyPrefix, KeyTemplate, key_name, parse_key
from pashe._internal.checks import parse_secret, validate_type
from pashe._internal.hooks import Hooks
from pashe._internal.locks.lock import lock_slots, parse_lock_holders, parse_lock_timeout, parse_lock_ttl

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pashe._internal.async_.tasks import AsyncDecorator
    from pashe.hooks import Hook
    from pashe.options import Duration


@final
class AsyncLocks:
    """Locks in a backend, held for every process over it: one holder at a time, or holders of them.

    The locks live under prefix + ``"__lock:"``, apart from the entries of a cache over the same
    backend and prefix. They close nothing: the backend belongs to whoever made it.

    Examples:
        >>> from pashe import AsyncLocks
        >>> from pashe.backends import AsyncMemoryBackend
        >>> locks = AsyncLocks(AsyncMemoryBackend(), prefix="app:")
        >>> async with locks.lock("report", ttl=30):
        ...     pass
    """

    __slots__ = ("_backend", "_hooks", "_key_secret")

    def __init__(
        self,
        backend: AsyncBackend,
        /,
        *,
        prefix: str = "",
        hooks: list[Hook] | tuple[Hook, ...] = (),
        key_secret: str | bytes | None = None,
    ) -> None:
        """Create the locks of backend.

        Args:
            backend: where the locks live.
            prefix: put in front of every lock, as a cache puts its own in front of its keys.
            hooks: what the locks tell about themselves: a release that fails goes to on_error.
            key_secret: the secret of ``{name:hmac}`` in the key templates of locked.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: key_secret is shorter than 16 bytes.
        """
        validate_type("backend", backend, AsyncBackend)
        validate_type("prefix", prefix, str)

        self._backend = AsyncPrefixedBackend(backend, prefix + KeyPrefix.LOCK)
        self._hooks = Hooks(hooks)
        self._key_secret = None if key_secret is None else parse_secret("key_secret", key_secret)

    def lock(
        self,
        key: str,
        /,
        *,
        ttl: Duration,
        timeout: Duration | None = None,
        holders: int = 1,
    ) -> AsyncLock:
        """Return the lock key for a ``with`` block, held in the backend for every process over it.

        Entering the block waits while holders others hold the lock; the lock is extended every
        third of ttl while the block runs, so the block may run longer than ttl, and released
        after; ttl frees it if its holder dies. A lock lost meanwhile raises LockLostError:
        a sync block runs to its end first, an async block is cancelled.

        Args:
            key: the name of the lock.
            ttl: how long the lock lives without an extension: seconds or a timedelta.
            timeout: the most entering the block waits: seconds or a timedelta; None waits as
                long as it takes.
            holders: how many may hold the lock at once, such as 3 for at most three reports
                built together; every use of a key takes the same holders.

        Returns:
            The lock, for a ``with`` block.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            LockTimeoutError: on entering the block, the lock stayed busy for timeout seconds.
            InvalidOptionsError: ttl is not positive, timeout is negative, or holders is less than 1.

        Examples:
            >>> from pashe import AsyncLocks
            >>> from pashe.backends import AsyncMemoryBackend
            >>> locks = AsyncLocks(AsyncMemoryBackend())
            >>> async with locks.lock("report", ttl=30):
            ...     pass
            >>> async with locks.lock("export", ttl=30, holders=3):
            ...     pass
        """
        validate_type("key", key, str)
        return AsyncLock(
            self._backend,
            key=key,
            ttl=parse_lock_ttl(ttl),
            timeout=parse_lock_timeout(timeout),
            holders=parse_lock_holders(holders),
            hooks=self._hooks,
        )

    async def try_lock(
        self,
        key: str,
        /,
        *,
        ttl: Duration,
        holders: int = 1,
    ) -> AsyncLock | None:
        """Take the lock key now if it is free, for a ``with`` block.

        The block releases it; a lock taken and never used in a block expires after ttl.

        Args:
            key: the name of the lock.
            ttl: how long the lock lives without an extension: seconds or a timedelta.
            holders: as in lock.

        Returns:
            The lock, taken, for a ``with`` block; None if holders others hold it.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive, or holders is less than 1.

        Examples:
            >>> from pashe import AsyncLocks
            >>> from pashe.backends import AsyncMemoryBackend
            >>> locks = AsyncLocks(AsyncMemoryBackend())
            >>> lock = await locks.try_lock("report", ttl=30)
            >>> await locks.try_lock("report", ttl=30) is None
            True
            >>> async with lock:
            ...     pass
        """
        validate_type("key", key, str)
        ttl = parse_lock_ttl(ttl)
        holders = parse_lock_holders(holders)

        lease = await atry_take(self._backend, lock_slots(key, holders), ttl, name=key, hooks=self._hooks)
        if lease is None:
            return None
        return AsyncLock(self._backend, key=key, ttl=ttl, holders=holders, lease=lease, hooks=self._hooks)

    def locked(
        self,
        *,
        ttl: Duration,
        key: str | None = None,
        timeout: Duration | None = None,
        holders: int = 1,
    ) -> AsyncDecorator:
        """Run every call of a function under a lock, as ``with locks.lock(...)`` around it.

        Args:
            ttl: as in lock.
            key: a str.format template over the arguments, such as ``"report:{report_id}"``; by
                default one lock for the function.
            timeout: as in lock.
            holders: as in lock: how many calls run at once.

        Returns:
            A decorator for a function of the side of the locks.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive, timeout is negative, or holders is less than 1.

        Examples:
            >>> from pashe import AsyncLocks
            >>> from pashe.backends import AsyncMemoryBackend
            >>> locks = AsyncLocks(AsyncMemoryBackend())
            >>> @locks.locked(ttl=30, key="report:{report_id}")
            ... async def build(report_id: int) -> int:
            ...     return report_id
            >>> await build(1)
            1
        """
        key_template = parse_key(key, key_secret=self._key_secret)
        ttl_seconds = parse_lock_ttl(ttl)
        timeout_seconds = parse_lock_timeout(timeout)
        holders = parse_lock_holders(holders)

        def decorator[**P, R](function: Callable[P, Awaitable[R]], /) -> Callable[P, Awaitable[R]]:
            validate_async(function, "decorate", self)
            keys = CallKeys(function, key_template or KeyTemplate(key_name(function), key_secret=self._key_secret), ())

            @functools.wraps(function)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                lock = AsyncLock(
                    self._backend,
                    key=keys.key(args, kwargs),
                    ttl=ttl_seconds,
                    timeout=timeout_seconds,
                    holders=holders,
                    hooks=self._hooks,
                )
                async with lock:
                    return await function(*args, **kwargs)

            return wrapper

        return decorator

    @override
    def __repr__(self) -> str:
        """Show the backend and the prefix of the locks."""
        backend, prefix = self._backend.backend, self._backend.prefix.removesuffix(KeyPrefix.LOCK)
        return f"{type(self).__name__}({backend!r}, prefix={prefix!r})"
