from __future__ import annotations

from typing import TYPE_CHECKING, Final, override

from pashe._internal.checks import parse_int, parse_seconds, parse_timeout

if TYPE_CHECKING:
    from pashe.errors import BackendError, LockLostError
    from pashe.hooks import Hook

_EXTENDS_PER_TTL: Final = 3  # a held lock is extended this many times within one ttl


class BaseLock:
    """What both locks share: the key, the ttl, the places in the backend and what a lost lock raises."""

    __slots__ = ("_hooks", "_key", "_lost", "_slots", "_timeout", "_ttl")

    def __init__(
        self,
        *,
        key: str,
        ttl: float,
        timeout: float | None,
        holders: int,
        hooks: Hook,
    ) -> None:
        """``ttl`` and timeout in seconds, as parse_lock_ttl and parse_lock_timeout gave them."""
        self._key = key
        self._ttl = ttl
        self._timeout = timeout
        self._slots = lock_slots(key, holders)
        self._hooks = hooks

        self._lost: BackendError | LockLostError | None = None  # the cause of the LockLostError the block raises

    @property
    def key(self) -> str:
        """The key of the lock, without the prefix of the cache."""
        return self._key

    @override
    def __repr__(self) -> str:
        """Show the key and the options of the lock."""
        options = f"ttl={self._ttl}, timeout={self._timeout}, holders={len(self._slots)}"
        return f"{type(self).__name__}({self._key!r}, {options})"

    @property
    def _extend_interval(self) -> float:
        return self._ttl / _EXTENDS_PER_TTL


def lock_slots(key: str, holders: int) -> tuple[str, ...]:
    """A key in the backend for each holder: the first is the key itself, as a lock of one holder keeps it."""
    return (key, *(f"{key}#{slot}" for slot in range(1, holders)))


def parse_lock_holders(holders: object) -> int:
    return parse_int("holders", holders, low=1, meaning="how many may hold the lock at once, 1 or more")


def parse_lock_ttl(ttl: object) -> float:
    return parse_seconds("ttl", ttl, "how long a lock lives without an extension", positive=True)


def parse_lock_timeout(timeout: object) -> float | None:
    return parse_timeout("timeout", timeout, "the most entering a lock waits")
