"""What a cache tells about itself, for metrics and logs: the hooks it calls, and what they get."""

from __future__ import annotations

import contextlib
import enum
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, final, override

from pashe._internal.checks import expect_type

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence


__all__ = [
    "CacheHeadersHook",
    "CacheStatus",
    "Circuit",
    "Failure",
    "Hook",
    "LoggingHook",
    "NearRead",
    "Operation",
    "Outcome",
    "RateLimitDecision",
]


class Hook:
    """What a cache tells about itself, for metrics and logs: subclass it and override what you need.

    Every method does nothing unless a subclass overrides it, so a hook written today keeps working
    when pashe tells of more. A cache, or a near cache, calls its hooks one after another, in the
    order it was given them, in the task or thread of the call. An error a hook raises is not
    caught: it is a bug of the hook, and goes up through the call it was raised in.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.hooks import Hook, Outcome
        >>> class PrintStatus(Hook):
        ...     def on_call(self, outcome: Outcome, /) -> None:
        ...         print(outcome.status.value)
        >>> cache = Cache(MemoryBackend(), hooks=[PrintStatus()])
        >>> @cache(ttl=60)
        ... def get_rate() -> float:
        ...     return 0.92
        >>> get_rate(), get_rate()
        miss
        hit
        (0.92, 0.92)
    """

    __slots__ = ()

    def on_call(self, outcome: Outcome, /) -> None:
        """Take how a cached call, or one item of a batch, was answered; nothing by default.

        Args:
            outcome: the function, the key, the status and the seconds the function ran.
        """

    def on_error(self, failure: Failure, /) -> None:
        """Take an error the cache works around instead of raising it; nothing by default.

        Such as a backend that fails while the source answers.

        Args:
            failure: what the cache was doing, with which key, and the error.
        """

    def on_rate_limit(self, decision: RateLimitDecision, /) -> None:
        """Take a call a rate limit counted: let through or refused; nothing by default.

        A call a failing backend let through uncounted goes to on_error instead.

        Args:
            decision: the key of the limit, and whether the call went through.
        """

    def on_near_read(self, read: NearRead, /) -> None:
        """Take a read of a near cache given the hook: how much its copies answered; nothing by default.

        Args:
            read: the keys its copies answered, and the keys it read from the shared backend.
        """

    def on_near_flush(self) -> None:
        """Take that a near cache given the hook dropped every copy; nothing by default.

        It does when it starts to listen to its bus, and whenever messages of the bus may have
        been lost: often, its copies answer seldom.
        """

    def on_circuit(self, circuit: Circuit, /) -> None:
        """Take that the Breaker of a backend opened or closed; nothing by default.

        Args:
            circuit: whether it opened, skipping the backend, or closed as the backend answered again.
        """


@final
class LoggingHook(Hook):
    """A hook that logs every error a cache works around, as a warning with its traceback.

    A cache raises no such error, so without this hook, or an on_error of yours, no one sees a
    backend that is down. Each record has the extra fields pashe_operation and pashe_key, for
    structured logs. While a backend is down every cached call logs one: filter or rate them in
    the logging of the application if that is too many.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.hooks import LoggingHook
        >>> cache = Cache(MemoryBackend(), hooks=[LoggingHook()])
    """

    __slots__ = ("_logger",)

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        """Create the hook.

        Args:
            logger: where to log; by default the logger ``pashe``.

        Raises:
            TypeError: logger is not a Logger.
        """
        expect_type("logger", logger, logging.Logger | None)

        self._logger = logger or logging.getLogger("pashe")

    @override
    def on_error(self, failure: Failure, /) -> None:
        self._logger.warning(
            "pashe: %s %r: %s",
            failure.operation.value,
            failure.key,
            failure.error,
            exc_info=failure.error,
            extra={"pashe_operation": failure.operation.value, "pashe_key": failure.key},
        )

    @override
    def on_circuit(self, circuit: Circuit, /) -> None:
        if circuit.open:
            self._logger.warning("pashe: the backend failed %d times in a row: skipped for a while", circuit.failures)
        else:
            self._logger.info("pashe: the backend answers again")


@final
class CacheHeadersHook(Hook):
    """Records the cached calls of each request for CacheHeadersMiddleware, which sets headers from them.

    Give the same hook to every cache the application calls and to the middleware. The calls of a
    cache without it are left out of Cache-Control and Cache-Status; ETag and 304 work either way.
    A call outside a request costs a single lookup.

    Examples:
        >>> from fastapi import FastAPI
        >>> from pashe import AsyncCache
        >>> from pashe.asgi import CacheHeadersMiddleware
        >>> from pashe.backends import AsyncMemoryBackend
        >>> from pashe.hooks import CacheHeadersHook
        >>> headers = CacheHeadersHook()
        >>> cache = AsyncCache(AsyncMemoryBackend(), hooks=[headers])
        >>> app = FastAPI()
        >>> app.add_middleware(CacheHeadersMiddleware, hook=headers)
    """

    __slots__ = ("_calls",)

    def __init__(self) -> None:
        """Create the hook, recording nothing until a middleware starts a request."""
        # A context variable: the threads of sync endpoints a request starts record into it too.
        self._calls: ContextVar[list[Outcome] | None] = ContextVar("pashe_request_calls", default=None)

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        calls = self._calls.get()
        if calls is not None:
            calls.append(outcome)

    @contextlib.contextmanager
    def recording(self) -> Generator[Sequence[Outcome]]:
        """Record the cached calls of the block, as a middleware does around a request.

        Yields:
            The outcomes of the calls, filled while the block runs.
        """
        calls: list[Outcome] = []
        token = self._calls.set(calls)
        try:
            yield calls
        finally:
            self._calls.reset(token)


@final
@dataclass(frozen=True, slots=True)
class Outcome:
    """How one call of a cached function, or one key of a batch, was answered.

    Attributes:
        function: the module and the qualified name of the cached function, such as
            ``app.users.get_user``: a label for metrics, the same for every call of it.
        key: the stored key, with the prefixes.
        status: how the call was answered.
        load_seconds: seconds the function ran for this call; 0 when it did not run.
        fresh_seconds: seconds the result of the call stays fresh from the call, negative for a
            stale answer; None when no result is stored.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.hooks import Hook
        >>> outcomes = []
        >>> class Record(Hook):
        ...     def on_call(self, outcome: Outcome, /) -> None:
        ...         outcomes.append(outcome)
        >>> cache = Cache(MemoryBackend(), prefix="app:", hooks=[Record()])
        >>> @cache(ttl=60, key="user:{user_id}")
        ... def get_user(user_id: int) -> int:
        ...     return user_id
        >>> get_user(1), get_user(1)
        (1, 1)
        >>> [(outcome.function.rpartition(".")[2], outcome.key, outcome.status.value) for outcome in outcomes]
        [('get_user', 'app:user:1', 'miss'), ('get_user', 'app:user:1', 'hit')]
    """

    function: str
    key: str
    status: CacheStatus
    load_seconds: float
    fresh_seconds: float | None


@enum.unique
class CacheStatus(enum.StrEnum):
    """How a call of a cached function was answered."""

    HIT = "hit"
    """A fresh stored result."""
    MISS = "miss"
    """The function ran."""
    STALE_WHILE_REVALIDATE = "stale-while-revalidate"
    """A stale result, answered while it is reloaded in the background."""
    STALE_IF_ERROR = "stale-if-error"
    """A stale result, answered instead of an error of the function."""
    STALE_IF_SLOW = "stale-if-slow"
    """A stale result, answered because the function was slow; the load goes on in the background."""
    NOT_FOUND = "not-found"
    """A cached "not found"."""
    FALLBACK = "fallback"
    """A result kept by the fallback backend of the cache, answered while the backend fails."""


@final
@dataclass(frozen=True, slots=True)
class Failure:
    """An error the cache worked around instead of raising it, and where.

    Attributes:
        operation: what the cache was doing.
        key: the key it was doing it with, with the prefixes; "" for a batch and for listening to a bus.
        error: the error: a PasheError of the cache, or the one the function raised, as it raised it.

    Examples:
        >>> import logging
        >>> from pashe.hooks import Hook
        >>> class LoggingHook(Hook):
        ...     def on_error(self, failure: Failure, /) -> None:
        ...         logging.warning("%s %r", failure.operation, failure.key, exc_info=failure.error)
    """

    operation: Operation
    key: str
    error: Exception

    @property
    def error_type(self) -> str:
        """The class of the error with its module, such as ``"pashe.errors.BackendError"``: a label for metrics."""
        kind = type(self.error)
        return f"{kind.__module__}.{kind.__qualname__}"


@enum.unique
class Operation(enum.StrEnum):
    """What a cache was doing when an error it worked around came: a label for metrics."""

    GET = "get"
    """A read of the backend."""
    GET_MANY = "get_many"
    """A read of the backend for a batch."""
    SET = "set"
    """A write to the backend."""
    SET_MANY = "set_many"
    """A write to the backend for a batch."""
    READ_TAGS = "read_tags"
    """A read of the counters of tags."""
    FALLBACK_GET = "fallback_get"
    """A read of the fallback, while the backend fails."""
    FALLBACK_SET = "fallback_set"
    """A write to the fallback, while the backend fails."""
    STAMPEDE_LOCK = "stampede_lock"
    """Taking the lock of a load, as Stampede.lock_for does."""
    REVALIDATION_LOCK = "revalidation_lock"
    """Taking the lock of a reload in the background."""
    RELEASE_LOCK = "release_lock"
    """Releasing a lock."""
    ENCODE = "encode"
    """Encoding a result: it is not stored."""
    DECODE = "decode"
    """Decoding a stored result: it is a miss."""
    TTL = "ttl"
    """Computing the TTL of a result from it: a negative one is not stored."""
    LOAD = "load"
    """A load that failed: a stale result answered instead of its error."""
    REVALIDATION = "revalidation"
    """A reload in the background."""
    RATE_LIMIT = "rate_limit"
    """Counting a call of a rate limit: it is let through; or taking back the count of a refused one, which stays."""
    PUBLISH = "publish"
    """Telling the other near caches through the bus which keys changed: their copies stay up to local_ttl."""
    LISTEN = "listen"
    """Listening to the bus, failed past a lost connection: every copy goes, and the bus listens again."""
    INVALIDATE = "invalidate"
    """Invalidating the tags of cache.invalidates after a write: their results stay up to their TTL."""


@final
@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """What a rate limit decided of a call it counted.

    Attributes:
        key: what the limit counts, as rate_limit was given it, such as ``"ip:203.0.113.7"``: for
            logs; too many values for a label of metrics.
        allowed: whether the call went through; False when it raised RateLimitedError.
    """

    key: str
    allowed: bool

    @property
    def label(self) -> Literal["allowed", "refused"]:
        """``"allowed"`` or ``"refused"``: a label for metrics."""
        return "allowed" if self.allowed else "refused"


@final
@dataclass(frozen=True, slots=True)
class NearRead:
    """One read of a near cache: get, or get_many with every key it was asked.

    Attributes:
        from_local: how many keys its copies in memory answered.
        from_shared: how many keys it read from the shared backend, found or not.
    """

    from_local: int
    from_shared: int

    @property
    def sources(self) -> dict[Literal["local", "shared"], int]:
        """The keys each source answered, ``"local"`` and ``"shared"``, without a source that answered none.

        Examples:
            >>> from pashe.hooks import NearRead
            >>> NearRead(from_local=2, from_shared=0).sources
            {'local': 2}
        """
        counts: dict[Literal["local", "shared"], int] = {"local": self.from_local, "shared": self.from_shared}
        return {source: count for source, count in counts.items() if count}


@final
@dataclass(frozen=True, slots=True)
class Circuit:
    """The Breaker of a backend opened or closed.

    Attributes:
        open: True when it opened: every call skips the backend for a while, as if it failed;
            False when it closed, as the backend answered again.
        failures: the failures in a row that opened it; 0 when it closed.
    """

    open: bool
    failures: int

    @property
    def state(self) -> Literal["open", "closed"]:
        """``"open"`` or ``"closed"``: a label for metrics."""
        return "open" if self.open else "closed"
