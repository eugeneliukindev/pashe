from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class AsyncBackend(ABC):
    """A place where entries live, such as memory or Redis. It stores bytes only.

    A ``ttl`` is in seconds and positive; ``None`` means no expiry. A miss is ``None``, not an
    error. Integers that ``incr`` keeps are signed 64-bit, as in Redis. A subclass implements
    every abstract method; ``get``, ``set`` and ``delete`` work through the batch methods unless
    it has faster ones. The sync and the async contract are the same, the methods of the async
    one awaited. A failure the caller cannot fix by changing the call raises BackendError.

    Examples:
        >>> from pashe.backends import AsyncMemoryBackend
        >>> backend = AsyncMemoryBackend()
        >>> await backend.set("k", b"v", ttl=60)
        >>> await backend.get("k")
        b'v'
    """

    __slots__ = ()

    async def get(self, key: str, /) -> bytes | None:
        """Return the value stored under key.

        Args:
            key: the key of the entry.

        Returns:
            The value, or None on a miss.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.get("missing") is None
            True
        """
        return (await self.get_many([key]))[0]

    @abstractmethod
    async def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        """Return the values of keys in their order.

        Args:
            keys: the keys of the entries.

        Returns:
            A value per key, None for a miss.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("a", b"1")
            >>> await backend.get_many(["a", "b"])
            [b'1', None]
        """
        raise NotImplementedError

    async def set(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> None:
        """Store value under key, replacing the entry and its TTL.

        Args:
            key: the key of the entry.
            value: the bytes to store.
            ttl: seconds the entry lives, positive; None means no expiry.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("k", b"v", ttl=60)
        """
        await self.set_many({key: value}, ttl=ttl)

    @abstractmethod
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        """Store all values with the same TTL.

        Args:
            values: the bytes to store under each key.
            ttl: seconds the entry lives, positive; None means no expiry.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set_many({"a": b"1", "b": b"2"}, ttl=60)
        """
        raise NotImplementedError

    @abstractmethod
    async def set_if_absent(
        self,
        key: str,
        value: bytes,
        /,
        *,
        ttl: float | None = None,
    ) -> bool:
        """Store value unless key holds another live value.

        A key that already holds this very value takes it again, as a repeat of a call whose
        answer was lost, such as one a client retried after a dropped connection, must not see
        its own write as someone else's; callers that compete make their values unique.

        Args:
            key: the key of the entry.
            value: the bytes to store.
            ttl: seconds the entry lives, positive; None means no expiry.

        Returns:
            Whether key holds value now.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set_if_absent("k", b"1"), await backend.set_if_absent("k", b"2")
            (True, False)
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str, /) -> bool:
        """Remove key.

        Args:
            key: the key of the entry.

        Returns:
            Whether the key existed.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("k", b"v")
            >>> await backend.delete("k"), await backend.delete("k")
            (True, False)
        """
        raise NotImplementedError

    @abstractmethod
    async def incr(
        self,
        key: str,
        by: int,
        /,
        *,
        ttl: float | None = None,
    ) -> int:
        """Add by to the integer under key, creating it from 0 if absent.

        The integer is stored as ASCII decimal, so ``get`` reads it back.

        Args:
            key: the key of the entry.
            by: what to add; negative to subtract.
            ttl: seconds the entry lives when it is created; an existing entry keeps its TTL.

        Returns:
            The integer after the addition.

        Raises:
            WrongTypeError: the value is not an integer.
            OverflowError: the result does not fit into 64 bits; the value is left as it was.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.incr("n", 5), await backend.incr("n", -7)
            (5, -2)
            >>> await backend.get("n")
            b'-2'
        """
        raise NotImplementedError

    @abstractmethod
    async def expire(self, key: str, ttl: float, /) -> bool:
        """Give key a new TTL from now.

        Args:
            key: the key of the entry.
            ttl: seconds the entry lives from now, positive.

        Returns:
            Whether the key existed.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("k", b"v")
            >>> await backend.expire("k", 60), await backend.expire("missing", 60)
            (True, False)
        """
        raise NotImplementedError

    @abstractmethod
    async def ttl(self, key: str, /) -> float | None:
        """Return the seconds key has left.

        Args:
            key: the key of the entry.

        Returns:
            The seconds, ``math.inf`` if the entry never expires, None on a miss.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("k", b"v")
            >>> await backend.ttl("k"), await backend.ttl("missing")
            (inf, None)
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        """Remove key only if its value equals value, at once: locks release with it.

        Args:
            key: the key of the entry.
            value: the value the entry must hold.

        Returns:
            Whether it removed the entry.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("lock", b"me")
            >>> await backend.delete_if_equals("lock", b"other"), await backend.delete_if_equals("lock", b"me")
            (False, True)
        """
        raise NotImplementedError

    @abstractmethod
    async def expire_if_equals(
        self,
        key: str,
        value: bytes,
        ttl: float,
        /,
    ) -> bool:
        """Give key a new TTL from now only if its value equals value, at once: locks extend with it.

        Args:
            key: the key of the entry.
            value: the value the entry must hold.
            ttl: seconds the entry lives from now, positive.

        Returns:
            Whether it gave the entry the new TTL.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.set("lock", b"me", ttl=10)
            >>> await backend.expire_if_equals("lock", b"me", 60)
            True
        """
        raise NotImplementedError

    @abstractmethod
    async def ping(self) -> None:
        """Check that the backend is reachable.

        Raises:
            BackendError: the backend cannot be reached.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.ping()
        """
        raise NotImplementedError

    @abstractmethod
    async def aclose(self) -> None:
        """Release what the backend owns, such as its client.

        Examples:
            >>> from pashe.backends import AsyncMemoryBackend
            >>> backend = AsyncMemoryBackend()
            >>> await backend.aclose()
        """
        raise NotImplementedError
