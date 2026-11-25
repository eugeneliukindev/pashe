from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pashe._internal.checks import parse_seconds, parse_timeout
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from pashe.errors import BackendError, LockLostError
    from pashe.hooks import Hook

_EXTENDS_PER_TTL: Final = 3  # a held lock is extended this many times within one ttl


class BaseLock:
    """What both locks share: the key, the ttl, the owner token and what a lost lock raises."""

    __slots__ = ("_hooks", "_key", "_lost", "_owner", "_timeout", "_ttl")

    def __init__(
        self,
        hooks: Hook,
        *,
        key: str,
        ttl: float,
        timeout: float | None,
        owner: bytes | None,
    ) -> None:
        # ttl and timeout in seconds, as parse_lock_ttl and parse_lock_timeout gave them
        self._hooks = hooks
        self._key = key
        self._ttl = ttl
        self._timeout = timeout
        self._owner = owner  # None until the lock is taken

        self._lost: BackendError | LockLostError | None = None  # the cause of the LockLostError the block raises

    @property
    def key(self) -> str:
        """The key of the lock, without the prefix of the cache."""
        return self._key

    @property
    def _extend_interval(self) -> float:
        return self._ttl / _EXTENDS_PER_TTL

    def _report_release_error(self, error: BackendError) -> None:
        self._hooks.on_error(Failure(Operation.RELEASE_LOCK, self._key, error))


def parse_lock_ttl(ttl: object) -> float:
    return parse_seconds("ttl", ttl, "how long a lock lives without an extension", positive=True)


def parse_lock_timeout(timeout: object) -> float | None:
    return parse_timeout("timeout", timeout, "the most entering a lock waits")
