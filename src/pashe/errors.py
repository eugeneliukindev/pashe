"""Errors pashe raises, and the warnings it gives."""

from typing import override

__all__ = [
    "BackendError",
    "CircuitOpenError",
    "CodecError",
    "InvalidOptionsError",
    "LockLostError",
    "LockTimeoutError",
    "MissingExtraError",
    "NotFoundError",
    "OneProcessWarning",
    "OverloadedError",
    "PasheError",
    "RateLimitedError",
    "ValueTooLargeError",
    "WrongTypeError",
]


class PasheError(Exception):
    """The base of every error pashe raises."""


class InvalidOptionsError(PasheError, ValueError):
    """Options that cannot work, such as a negative limit."""


class WrongTypeError(PasheError, TypeError):
    """An entry holds data the operation cannot use, such as ``incr`` on a value that is not an integer."""


class ValueTooLargeError(PasheError):
    """A value that does not fit into ``max_bytes`` of a memory backend even alone; it is not stored.

    Attributes:
        size: the bytes the key and the value take together.
        max_bytes: the most bytes the backend keeps.

    Examples:
        >>> from pashe.errors import ValueTooLargeError
        >>> print(ValueTooLargeError(2048, 1024))
        2048 bytes do not fit into max_bytes 1024
    """

    size: int
    max_bytes: int

    def __init__(self, size: int, max_bytes: int) -> None:
        """Create the error.

        Args:
            size: the bytes the key and the value take together.
            max_bytes: the most bytes the backend keeps.
        """
        super().__init__(size, max_bytes)  # the arguments, not the message: pickle calls it again with them

        self.size = size
        self.max_bytes = max_bytes

    @override
    def __str__(self) -> str:
        return f"{self.size} bytes do not fit into max_bytes {self.max_bytes}"


class NotFoundError(PasheError, LookupError):
    """A cached function raised, or negative caching kept, the answer "there is no such data".

    When the function raised it, the exception of the function is the ``__cause__``. The basic API does
    not raise it: ``get`` returns None on a miss.

    Attributes:
        key: the key of the call, without the prefix of the cache.

    Examples:
        >>> from pashe.errors import NotFoundError
        >>> print(NotFoundError("user:1"))
        'user:1' was not found
    """

    key: str

    def __init__(self, key: str) -> None:
        """Create the error.

        Args:
            key: the key of the call, without the prefix of the cache.
        """
        super().__init__(key)  # the arguments, not the message: pickle calls it again with them

        self.key = key

    @override
    def __str__(self) -> str:
        return f"{self.key!r} was not found"


class BackendError(PasheError):
    """The backend failed or cannot be reached; the error of its client is the ``__cause__``.

    A backend raises it for every failure the caller cannot fix by changing the call.
    """


class CodecError(PasheError):
    """A value could not be turned into bytes, or bytes into a value of the asked type."""


class LockLostError(PasheError):
    """A lock expired before its holder extended it; someone else may hold it now.

    Attributes:
        key: the name of the lock.
        expired: True when the backend no longer had it, False when the backend failed to extend it.

    Examples:
        >>> from pashe.errors import LockLostError
        >>> print(LockLostError("report", expired=True))
        the lock 'report' expired
    """

    key: str
    expired: bool

    def __init__(self, key: str, *, expired: bool = False) -> None:
        """Create the error.

        Args:
            key: the name of the lock.
            expired: True when the backend no longer had it, False when the backend failed to extend it.
        """
        super().__init__(key)  # pickle calls it again with the key and then restores expired from the attributes

        self.key = key
        self.expired = expired

    @override
    def __str__(self) -> str:
        return f"the lock {self.key!r} expired" if self.expired else f"the lock {self.key!r} was lost while held"


class CircuitOpenError(BackendError):
    """The Breaker of the backend is open after the backend failed: the call skipped it, without a wait.

    Attributes:
        failures: the failures in a row that opened it.

    Examples:
        >>> from pashe.errors import CircuitOpenError
        >>> print(CircuitOpenError(5))
        the backend is skipped: it failed 5 times in a row
    """

    failures: int

    def __init__(self, failures: int) -> None:
        """Create the error.

        Args:
            failures: the failures in a row that opened it.
        """
        super().__init__(failures)  # the arguments, not the message: pickle calls it again with them

        self.failures = failures

    @override
    def __str__(self) -> str:
        return f"the backend is skipped: it failed {self.failures} times in a row"


class LockTimeoutError(PasheError, TimeoutError):
    """A lock stayed busy for the whole timeout of the wait.

    Attributes:
        key: the name of the lock.
        timeout: the seconds the wait took; only a wait with a timeout ends with this error.

    Examples:
        >>> from pashe.errors import LockTimeoutError
        >>> print(LockTimeoutError("report", 5.0))
        the lock 'report' stayed busy for 5.0s
    """

    key: str
    timeout: float | None

    def __init__(self, key: str, timeout: float | None) -> None:
        """Create the error.

        Args:
            key: the name of the lock.
            timeout: the seconds the wait took.
        """
        super().__init__(key, timeout)  # the arguments, not the message: pickle calls it again with them

        self.key = key
        self.timeout = timeout

    @override
    def __str__(self) -> str:
        return f"the lock {self.key!r} stayed busy for {self.timeout}s"


class RateLimitedError(PasheError):
    """A call over its rate limit.

    Attributes:
        retry_after: seconds until a call would pass again if no other calls come, for a
            ``Retry-After`` header.

    Examples:
        >>> from pashe.errors import RateLimitedError
        >>> RateLimitedError(1.5).retry_after
        1.5
    """

    retry_after: float

    def __init__(self, retry_after: float) -> None:
        """Create the error.

        Args:
            retry_after: seconds until a call would pass again if no other calls come, for a
                ``Retry-After`` header.
        """
        super().__init__(retry_after)  # the arguments, not the message: pickle calls it again with them

        self.retry_after = retry_after

    @override
    def __str__(self) -> str:
        return f"rate limited, retry after {self.retry_after:.3f}s"


class OverloadedError(PasheError):
    """A load refused by ``Stampede.max_loads``: every slot was taken and an old result can answer."""

    @override
    def __str__(self) -> str:
        return "every load slot is taken"


class MissingExtraError(PasheError, ModuleNotFoundError):
    """A module of pashe.contrib imported without its extra; the message says how to install it.

    Attributes:
        module: the module of pashe that needs the extra.
        extra: the extra of pashe the module needs.

    Examples:
        >>> from pashe.errors import MissingExtraError
        >>> print(MissingExtraError("pashe.contrib.orjson", "orjson", name="orjson"))
        pashe.contrib.orjson needs the orjson extra: pip install "pashe[orjson]" or uv add "pashe[orjson]"
    """

    module: str
    extra: str

    def __init__(
        self,
        module: str,
        extra: str,
        *,
        name: str | None = None,
    ) -> None:
        """Create the error.

        Args:
            module: the module of pashe that needs the extra.
            extra: the extra of pashe the module needs.
            name: the dependency that failed to import, as ModuleNotFoundError has it.
        """
        super().__init__(module, extra, name=name)  # the arguments, not the message: pickle calls it again with them

        self.module = module
        self.extra = extra

    @override
    def __str__(self) -> str:
        return f'{self.module} needs the {self.extra} extra: pip install "pashe[{self.extra}]" or uv add "pashe[{self.extra}]"'


class OneProcessWarning(UserWarning):
    """An option that shares across processes, over a backend that lives in one process.

    It works, but adds nothing there, such as ``Stampede.lock_for`` over a MemoryBackend, where
    ``share_loads`` already shares the load. Tests that swap the shared backend for memory can
    silence it alone: ``filterwarnings = ["ignore::pashe.errors.OneProcessWarning"]``.
    """
