from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final, Self, final

from pashe._internal.async_.backends.backend import AsyncBackend
from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
from pashe._internal.async_.cache.around import (
    AsyncInvalidatingDecorator,
    AsyncLockedDecorator,
    AsyncRateLimitedDecorator,
)
from pashe._internal.async_.cache.cached import AsyncCachedFunctionDecorator, AsyncCachedValueDecorator
from pashe._internal.async_.cache.cached_batch import AsyncCachedBatchFunctionDecorator
from pashe._internal.async_.cache.fallback import AsyncBackendFallbackStore, AsyncFallbackStore, AsyncNoOpFallbackStore
from pashe._internal.async_.cache.tags import AsyncTags
from pashe._internal.async_.limiter import AsyncRateLimiter
from pashe._internal.async_.locks.lock import AsyncLock
from pashe._internal.async_.locks.locking import atry_acquire
from pashe._internal.async_.tasks import AsyncBackgroundTasks
from pashe._internal.cache.entry import Serializer
from pashe._internal.cache.keys import KeyPrefix, KeyTemplate
from pashe._internal.cache.policy import Policy
from pashe._internal.checks import FUNCTION, duration_seconds, expect_item_types, expect_type, parse_secret, parse_ttl
from pashe._internal.hooks import AllHooks
from pashe._internal.limits import LIMIT, parse_cost
from pashe._internal.locks.lock import parse_lock_timeout, parse_lock_ttl
from pashe.codecs import Codec, JsonCodec
from pashe.compressors import Compressor, NoOpCompressor
from pashe.errors import InvalidOptionsError
from pashe.hooks import Hook
from pashe.options import Fallback, Negative, Stale, Stampede, Store

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from pashe.options import TTL, Duration
    from pashe.ratelimit import Limit, RateLimitState


_TTL_MEANING: Final = "how long a result is fresh"


@final
class AsyncCache:
    """Caches the results of functions in a backend and guards calls with locks and rate limits.

    Entries, tags, locks and limits live in the backend, shared by every cache over it; single
    flights live in memory. The cache of the other side, for the functions of that side over its
    backends, has the same methods: on the async side they are awaited.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> cache = AsyncCache(AsyncMemoryBackend(), prefix="app:")
        >>> @cache(ttl=60, key="user:{user_id}")
        ... async def get_user(user_id: int) -> dict[str, int]:
        ...     return {"id": user_id}
        >>> await get_user(1)
        {'id': 1}
        >>> await cache.aclose()
    """

    __slots__ = (
        "_backend",
        "_background",
        "_clock",
        "_fallback",
        "_hooks",
        "_key_secret",
        "_limiter",
        "_locks",
        "_serializer",
        "_tags",
    )

    def __init__(  # noqa: WPS213 - a cache checks and wires every option it takes
        self,
        backend: AsyncBackend,
        /,
        *,
        prefix: str = "",
        codec: Codec = JsonCodec(),
        hooks: list[Hook] | tuple[Hook, ...] = (),
        fallback: Fallback[AsyncBackend] | None = None,
        compressor: Compressor = NoOpCompressor(),
        key_secret: str | bytes | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Create a cache over backend; closing the cache closes it and the fallback.

        Args:
            backend: where entries live.
            prefix: put in front of every key, the cache's own included, so services can share a
                backend. The cache keeps its own keys under ``prefix + "__"``: keys of yours must
                not start with ``"__"``.
            codec: the format of stored values.
            hooks: what the cache tells about itself, for metrics and logs: each Hook gets how
                every call was answered, and the errors the cache works around.
            fallback: where cached functions keep their results while the backend fails, and for
                how long: a Fallback over a backend of the side of the cache; none by default.
            compressor: shrinks stored values from its min_size; NoOpCompressor, which stores them as
                they are, by default.
            key_secret: the secret of ``{name:hmac}`` in the templates of keys and tags: the same
                for every cache over the backend, kept out of it, at least 16 bytes. Changing it makes
                every such key a miss.
            clock: wall-clock seconds, for tests.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: key_secret is shorter than 16 bytes.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> from pashe.options import Fallback
            >>> from pashe.compressors import GzipCompressor
            >>> from pashe.hooks import Failure, Hook
            >>> class PrintErrors(Hook):
            ...     def on_error(self, failure: Failure, /) -> None:
            ...         print(failure.operation, failure.error)
            >>> cache = AsyncCache(
            ...     AsyncMemoryBackend(),
            ...     prefix="app:",
            ...     compressor=GzipCompressor(),
            ...     fallback=Fallback(AsyncMemoryBackend()),
            ...     hooks=[PrintErrors()],
            ... )
        """
        expect_type("backend", backend, AsyncBackend)
        expect_type("prefix", prefix, str)
        expect_type("codec", codec, Codec)
        expect_type("hooks", hooks, list | tuple)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        expect_item_types("hooks", hooks, Hook)
        expect_type("fallback", fallback, Fallback | None)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        if fallback is not None:
            expect_type("Fallback.backend", fallback.backend, AsyncBackend)
        expect_type("compressor", compressor, Compressor)
        expect_type("key_secret", key_secret, str | bytes | None)
        expect_type("clock", clock, FUNCTION)

        self._backend = AsyncPrefixedBackend(backend, prefix)
        self._hooks = AllHooks(tuple(hooks))
        self._fallback: AsyncFallbackStore = (
            AsyncNoOpFallbackStore()
            if fallback is None
            else AsyncBackendFallbackStore(
                AsyncPrefixedBackend(fallback.backend, prefix),  # under the prefix of the cache, as its backend is
                ttl=duration_seconds(fallback.ttl),  # Fallback checked it
                hooks=self._hooks,
            )
        )
        self._key_secret = None if key_secret is None else parse_secret("key_secret", key_secret)
        self._clock = clock

        self._serializer = Serializer(codec, compressor)
        self._locks = AsyncPrefixedBackend(backend, prefix + KeyPrefix.LOCK)  # apart from the keys of results
        self._background = AsyncBackgroundTasks()
        self._tags = AsyncTags(self._backend)
        self._limiter = AsyncRateLimiter(self._backend, self._hooks, self._clock)

    def __call__(
        self,
        *,
        ttl: TTL,
        key: str | None = None,
        tags: list[str] | tuple[str, ...] = (),
        stale: Stale = Stale(),
        stampede: Stampede = Stampede(),
        negative: Negative = Negative(),
        store: Store = Store(),
    ) -> AsyncCachedFunctionDecorator:
        """Cache the results of a function, as ``@cache(ttl=60)``; the function is the loader.

        The function is of the side of the cache. The result is decoded as its return annotation;
        without one, as what the codec reads back on its own. Every duration is seconds or a
        timedelta. The groups are in pashe.options; one left out takes its defaults.

        Args:
            ttl: how long a result is fresh: seconds or a timedelta; 0 keeps a result only for
                the stale windows. A function of the result computes it for each result, such as
                ``lambda token: token.expires_in - 60``; a result it gives a negative TTL is not
                stored and goes to on_error.
            key: a str.format template over the arguments by name, such as ``"user:{user_id}"``;
                by default the qualified name of the function and the repr of its arguments,
                which must then be str, int, float, bool, None, date, time, datetime, UUID,
                Decimal or enums of them. A field of a template takes the same, or any value
                with a digest, such as ``{filters:blake2b}``. A lambda needs one; functions of one
                name made by one factory share their keys without it.
            tags: templates like key; invalidate_tags of any of them makes the result a miss. A list
                or a tuple; a str is refused, as it would split into letters.
            stale: how long after the TTL a stale result still answers, and in which cases.
            stampede: how the loads of a key are shared and spread: revalidate_before, jitter,
                single_flight, lock_for, max_concurrent_loads.
            negative: loader errors that mean "there is no such data", kept as the answer for a
                while; by default Negative() keeps none.
            store: which loaded results are stored; by default every one.

        Returns:
            A decorator for a function of the side of the cache; it returns the cached function.

        Raises:
            InvalidOptionsError: the options cannot work together.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> from pashe.options import Stale
            >>> @cache(ttl=60, key="user:{user_id}", tags=["users"], stale=Stale(while_revalidate=30))
            ... async def get_user(user_id: int) -> dict[str, int]:
            ...     return {"id": user_id}
            >>> await get_user(1)
            {'id': 1}
        """
        ttl = parse_ttl("ttl", ttl, _TTL_MEANING)
        expect_type("key", key, str | None)
        # not a str, which would split into one tag per letter; isinstance takes no list[str]
        expect_type("tags", tags, list | tuple)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        expect_item_types("tags", tags, str)
        expect_type("stale", stale, Stale)
        expect_type("stampede", stampede, Stampede)
        expect_type("negative", negative, Negative)
        expect_type("store", store, Store)

        policy = Policy.of(
            ttl=ttl,
            stale=stale,
            stampede=stampede,
            negative=negative,
            store=store,
            clock=self._clock,
        )
        return AsyncCachedFunctionDecorator(
            policy,
            key=None if key is None else KeyTemplate(key, secret=self._key_secret),
            tags=tuple(KeyTemplate(tag, secret=self._key_secret) for tag in tags),
            serializer=self._serializer,
            backend=self._backend,
            tag_store=self._tags,
            fallback=self._fallback,
            background=self._background,
            hooks=self._hooks,
        )

    def value(
        self, *, ttl: TTL, key: str | None = None, tags: list[str] | tuple[str, ...] = ()
    ) -> AsyncCachedValueDecorator:
        """Keep values of yours that no function loads, as ``@cache.value(ttl=600)``.

        For what one place writes and another reads later, such as a session, a one-time code or
        the result of a job: a miss is None, not a load. The function never runs: its parameters
        fill the templates, and its return annotation says what a value decodes as.

        Args:
            ttl: how long a value lives, as in ``@cache(...)``.
            key: a template over the arguments by name, as in ``@cache(...)``.
            tags: templates like key, as in ``@cache(...)``.

        Returns:
            A decorator for a function of the side of the cache; it returns the AsyncCachedValue of the function.

        Raises:
            InvalidOptionsError: the options cannot work together.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.value(ttl=3600, key="session:{sid}", tags=["user:{user_id}"])
            ... async def session(sid: str, user_id: int) -> dict[str, str]:
            ...     raise NotImplementedError  # the function of a value never runs
            >>> await session.set({"theme": "dark"}, "abc", 1)
            >>> await session.get("abc", 1)
            {'theme': 'dark'}
        """
        return AsyncCachedValueDecorator(self(ttl=ttl, key=key, tags=tags))

    def batch(
        self,
        *,
        ttl: TTL,
        key: str | None = None,
        stampede: Stampede = Stampede(),
        store: Store = Store(),
    ) -> AsyncCachedBatchFunctionDecorator:
        """Cache the results of a batch function ``f(items: list[K]) -> dict[K, V]`` per item.

        A call reads every item in one backend call and calls the function once with the missing
        ones; items it leaves out are absent from the result and not stored.

        Args:
            ttl: as in ``@cache(...)``.
            key: a str.format template over the item, such as ``"user:{}"``; by default the
                qualified name of the function and the repr of the item.
            stampede: its jitter, and max_concurrent_loads: how many batches may load at once in
                this cache. A batch shares no loads and reloads nothing in the background: lock_for and
                revalidate_before are refused, single_flight unused.
            store: as in ``@cache(...)``; slower_than is of the load of the whole batch.

        Returns:
            A decorator for a batch function of the side of the cache; it returns the cached batch
            function.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: the options cannot work together.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.batch(ttl=60, key="user:{}")
            ... async def get_users(user_ids: list[int]) -> dict[int, dict[str, int]]:
            ...     return {user_id: {"id": user_id} for user_id in user_ids}
            >>> await get_users([1, 2])
            {1: {'id': 1}, 2: {'id': 2}}
        """
        ttl = parse_ttl("ttl", ttl, _TTL_MEANING)
        expect_type("key", key, str | None)
        expect_type("stampede", stampede, Stampede)
        expect_type("store", store, Store)

        policy = Policy.of(
            ttl=ttl,
            stale=Stale(),
            stampede=stampede,
            negative=Negative(),
            store=store,
            clock=self._clock,
        )
        if policy.stampede.lock_for:
            msg = "a batch shares no loads: its Stampede takes no lock_for"
            raise InvalidOptionsError(msg)
        if policy.stampede.revalidate_before:
            msg = "a batch reloads nothing in the background: its Stampede takes no revalidate_before"
            raise InvalidOptionsError(msg)
        return AsyncCachedBatchFunctionDecorator(
            policy,
            key=None if key is None else KeyTemplate(key, secret=self._key_secret),
            serializer=self._serializer,
            backend=self._backend,
            fallback=self._fallback,
            hooks=self._hooks,
        )

    def key_for(self, template: str, /, *args: object, **kwargs: object) -> str:
        """Return template filled as the cache fills its keys and tags, with the same digests.

        invalidate_tags takes tags as they are stored, so a tag with a digest, such as
        ``"user:{email:hmac}"``, is made here.

        Args:
            template: a template, such as ``"user:{email:hmac}"``.
            *args: the values of ``{}`` and ``{0}``.
            **kwargs: the values of ``{name}``.

        Returns:
            The filled template.

        Raises:
            InvalidOptionsError: the template names an unknown digest, or hmac without a secret.
            TypeError: a value has no canonical form to hash.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend(), key_secret="a secret of sixteen bytes or more")
            >>> cache.key_for("user:{email:hmac}", email="ada@example.com")
            'user:...'
            >>> cache.key_for("user:{email:hmac}", email="ada@example.com") == cache.key_for(
            ...     "user:{email:hmac}", email="ada@example.com"
            ... )
            True
        """
        expect_type("template", template, str)
        return KeyTemplate(template, secret=self._key_secret).render(args, kwargs)

    async def invalidate_tags(self, *tags: str) -> None:
        """Make every result stored with one of tags a miss: two calls to the backend per tag, no scan.

        Args:
            *tags: the tags, as the templates of ``tags=`` filled in.

        Raises:
            TypeError: an argument is not of the type its annotation names.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache(ttl=60, tags=["user:{user_id}"])
            ... async def get_user(user_id: int) -> dict[str, int]:
            ...     return {"id": user_id}
            >>> await cache.invalidate_tags("user:1")
        """
        expect_item_types("tags", tags, str)
        await self._tags.invalidate(tags)

    def invalidates(self, *, tags: list[str] | tuple[str, ...]) -> AsyncInvalidatingDecorator:
        """Invalidate tags after every call of a function that writes, as invalidate_tags would.

        The tags are filled from the arguments of each call, as those of ``@cache(...)``, and
        invalidated whether the call returns or raises: a write that raised may have changed data
        all the same, and a needless miss costs less than a stale result. An error of the backend
        goes to on_error, so the call returns or raises as it would without the decorator.

        Args:
            tags: templates like those of ``tags=``, such as ``["user:{user_id}"]``; a list or a tuple.

        Returns:
            A decorator for a function of the side of the cache; it raises InvalidOptionsError
            for a template that names no parameter of the function.

        Raises:
            TypeError: tags is not a list or a tuple of str.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache(ttl=60, tags=["user:{user_id}"])
            ... async def get_user(user_id: int) -> dict[str, int]:
            ...     return {"id": user_id}
            >>> @cache.invalidates(tags=["user:{user_id}"])
            ... async def rename_user(user_id: int, name: str) -> str:
            ...     return name
            >>> await rename_user(1, "Ada")
            'Ada'
        """
        expect_type("tags", tags, list | tuple)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        expect_item_types("tags", tags, str)
        return AsyncInvalidatingDecorator(
            tuple(KeyTemplate(tag, secret=self._key_secret) for tag in tags), self._tags, hooks=self._hooks
        )

    def lock(self, key: str, /, *, ttl: Duration, timeout: Duration | None = None) -> AsyncLock:
        """Return the lock key for a ``with`` block, held in the backend for every cache over it.

        Entering the block waits while someone else holds the lock; the lock is extended every
        third of ttl while the block runs, so the block may run longer than ttl, and released
        after; ttl frees it if its holder dies. A lock lost meanwhile raises LockLostError:
        a sync block runs to its end first, an async block is cancelled.

        Args:
            key: the name of the lock.
            ttl: how long the lock lives without an extension: seconds or a timedelta.
            timeout: the most entering the block waits: seconds or a timedelta; None waits as
                long as it takes.

        Returns:
            The lock, for a ``with`` block.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            LockTimeoutError: on entering the block, the lock stayed busy for timeout seconds.
            InvalidOptionsError: ttl is not positive, or timeout is negative.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> async with cache.lock("report", ttl=30):
            ...     pass
        """
        expect_type("key", key, str)
        return AsyncLock(
            self._locks, self._hooks, key=key, ttl=parse_lock_ttl(ttl), timeout=parse_lock_timeout(timeout)
        )

    async def try_lock(self, key: str, /, *, ttl: Duration) -> AsyncLock | None:
        """Take the lock key now if it is free, for a ``with`` block.

        The block releases it; a lock taken and never used in a block expires after ttl.

        Args:
            key: the name of the lock.
            ttl: how long the lock lives without an extension: seconds or a timedelta.

        Returns:
            The lock, taken, for a ``with`` block; None if someone else holds it.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> lock = await cache.try_lock("report", ttl=30)
            >>> await cache.try_lock("report", ttl=30) is None
            True
            >>> async with lock:
            ...     pass
        """
        expect_type("key", key, str)
        ttl = parse_lock_ttl(ttl)
        owner = await atry_acquire(self._locks, key, ttl)
        return None if owner is None else AsyncLock(self._locks, self._hooks, key=key, ttl=ttl, owner=owner)

    async def rate_limit(
        self, key: str, limit: Limit, /, *, cost: int = 1, fail_open: bool = True
    ) -> RateLimitState | None:
        """Count a call for key in the backend, and return what is left of the limit.

        Call it before the work it guards. A failing backend lets the call through uncounted,
        returns None and goes to on_error.

        Args:
            key: what the limit counts, such as ``f"ip:{ip}"``.
            limit: the limit, such as ``per_minute(100)``.
            cost: how many calls this one counts as, such as 5 for a heavy request.
            fail_open: let a call through when the backend fails; off, raise BackendError instead,
                for limits that guard against abuse.

        Returns:
            What is left of the limit after this call; None if the backend failed and the call
            went through uncounted.

        Raises:
            RateLimitedError: the key is over limit; retry_after says for how long.
            BackendError: the backend failed and fail_open is off.
            WrongTypeError: a counter of the limit holds what is not an integer, such as a value
                another program wrote under its key: fail_open lets through an outage, not that.
            InvalidOptionsError: cost is not from 1 to the calls of the limit.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> from pashe.ratelimit import per_minute
            >>> state = await cache.rate_limit("ip:203.0.113.7", per_minute(100))
            >>> state.remaining
            99
        """
        expect_type("key", key, str)
        expect_type("limit", limit, LIMIT)
        cost = parse_cost(limit, cost)
        expect_type("fail_open", fail_open, bool)
        return await self._limiter.count(key, limit, cost=cost, fail_open=fail_open)

    def locked(self, *, ttl: Duration, key: str | None = None, timeout: Duration | None = None) -> AsyncLockedDecorator:
        """Run every call of a function under a lock, as ``with cache.lock(...)`` around it.

        Args:
            ttl: as in lock.
            key: a str.format template over the arguments, such as ``"report:{report_id}"``; by
                default one lock for the function.
            timeout: as in lock.

        Returns:
            A decorator for a function of the side of the cache.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive, or timeout is negative.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.locked(ttl=30, key="report:{report_id}")
            ... async def build(report_id: int) -> int:
            ...     return report_id
            >>> await build(1)
            1
        """
        expect_type("key", key, str | None)
        template = None if key is None else KeyTemplate(key, secret=self._key_secret)
        return AsyncLockedDecorator(
            self, template, self._key_secret, ttl=parse_lock_ttl(ttl), timeout=parse_lock_timeout(timeout)
        )

    def rate_limited(self, limit: Limit, /, *, key: str | None = None) -> AsyncRateLimitedDecorator:
        """Count every call of a function with rate_limit before it runs.

        Args:
            limit: the limit, such as ``per_minute(10)``.
            key: a template like that of locked; by default one limit for the function.

        Returns:
            A decorator for a function of the side of the cache; the function raises
            RateLimitedError over the limit.

        Raises:
            TypeError: an argument is not of the type its annotation names.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> from pashe.ratelimit import per_minute
            >>> @cache.rate_limited(per_minute(10), key="export:{user_id}")
            ... async def export(user_id: int) -> int:
            ...     return user_id
            >>> await export(1)
            1
        """
        expect_type("limit", limit, LIMIT)
        expect_type("key", key, str | None)
        template = None if key is None else KeyTemplate(key, secret=self._key_secret)
        return AsyncRateLimitedDecorator(self, template, self._key_secret, limit=limit)

    async def ping(self) -> None:
        """Check that the backend is reachable.

        Raises:
            BackendError: the backend cannot be reached.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> await cache.ping()
        """
        await self._backend.ping()

    async def aclose(self) -> None:
        """Wait for the background reloads, then close the backend and the fallback.

        The cache owns what it was given, as a backend owns its client.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> await cache.aclose()
        """
        await self._background.aclose()
        await self._backend.aclose()
        await self._fallback.aclose()

    async def __aenter__(self) -> Self:
        """Return the cache."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the cache."""
        await self.aclose()
