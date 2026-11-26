from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Self, final, override

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
from pashe._internal.async_.cache.storage import AsyncStorage
from pashe._internal.async_.cache.tags import AsyncTags
from pashe._internal.async_.limiter import AsyncRateLimiter
from pashe._internal.async_.locks.lock import AsyncLock
from pashe._internal.async_.locks.locking import atry_take
from pashe._internal.async_.tasks import AsyncBackgroundTasks
from pashe._internal.cache.keys import KeyPrefix, KeyTemplate, parse_key, parse_tags
from pashe._internal.cache.policy import Policy
from pashe._internal.checks import FUNCTION, duration_seconds, expect_item_types, expect_type, parse_secret
from pashe._internal.hooks import Hooks
from pashe._internal.limits import LIMIT, parse_cost
from pashe._internal.locks.lock import lock_slots, parse_lock_holders, parse_lock_timeout, parse_lock_ttl
from pashe.codecs import Codec, JsonCodec
from pashe.compressors import Compressor, NoOpCompressor
from pashe.options import Fallback, Negative, Stale, Stampede, Store

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from pashe.hooks import Hook
    from pashe.options import TTL, Duration
    from pashe.ratelimit import Limit, RateLimitState


@final
class AsyncCache:
    """Caches the results of functions in a backend and guards calls with locks and rate limits.

    Entries, tags, locks and limits live in the backend, shared by every cache over it; shared
    loads live in memory. The cache of the other side, for the functions of that side over its
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
        "_codec",
        "_compressor",
        "_fallback",
        "_hooks",
        "_key_secret",
        "_limiter",
        "_lock_backend",
        "_storage",
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
        expect_type("fallback", fallback, Fallback | None)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        if fallback is not None:
            expect_type("Fallback.backend", fallback.backend, AsyncBackend)
        expect_type("compressor", compressor, Compressor)
        expect_type("key_secret", key_secret, str | bytes | None)
        expect_type("clock", clock, FUNCTION)

        self._backend = AsyncPrefixedBackend(backend, prefix)
        self._codec = codec
        self._hooks = Hooks(hooks)
        self._fallback: AsyncFallbackStore = (
            AsyncNoOpFallbackStore()
            if fallback is None
            else AsyncBackendFallbackStore(
                AsyncPrefixedBackend(fallback.backend, prefix),  # under the prefix of the cache, as its backend is
                ttl=duration_seconds(fallback.ttl),  # Fallback checked it
                hooks=self._hooks,
            )
        )
        self._compressor = compressor
        self._key_secret = None if key_secret is None else parse_secret("key_secret", key_secret)
        self._clock = clock

        self._lock_backend = AsyncPrefixedBackend(backend, prefix + KeyPrefix.LOCK)  # apart from the keys of results
        self._background = AsyncBackgroundTasks()
        self._tags = AsyncTags(self._backend)
        self._storage = AsyncStorage(self._backend, tags=self._tags, fallback=self._fallback, hooks=self._hooks)
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
        """Cache the results of a function, as ``@cache(ttl=60)``.

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
                share_loads, lock_for, max_loads.
            negative: errors of the function that mean "there is no such data", kept as the answer for a
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
            key_template=parse_key(key, secret=self._key_secret),
            tag_templates=parse_tags(tags, secret=self._key_secret),
            codec=self._codec,
            compressor=self._compressor,
            storage=self._storage,
            tags=self._tags,
            backend=self._backend,
            background=self._background,
            hooks=self._hooks,
        )

    def value(
        self,
        *,
        ttl: TTL,
        key: str | None = None,
        tags: list[str] | tuple[str, ...] = (),
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
        tags: list[str] | tuple[str, ...] = (),
        stale: Stale = Stale(),
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
            tags: templates over the item like key, such as ``["user:{}"]``: invalidate_tags of
                one makes the result of its item a miss, as of ``@cache(...)``.
            stale: its if_error: when the batch function raises, the stale results of its items
                answer, if each item has one, and the error goes to on_error. A batch waits for its
                load and reloads nothing in the background: while_revalidate and if_slow are refused.
            stampede: its jitter, and max_loads: how many batches may load at once in
                this cache. A batch shares no loads and reloads nothing in the background: lock_for and
                revalidate_before are refused, share_loads unused.
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
        policy = Policy.of_batch(
            ttl=ttl,
            stale=stale,
            stampede=stampede,
            store=store,
            clock=self._clock,
        )
        return AsyncCachedBatchFunctionDecorator(
            policy,
            key_template=parse_key(key, secret=self._key_secret),
            tag_templates=parse_tags(tags, secret=self._key_secret),
            codec=self._codec,
            compressor=self._compressor,
            storage=self._storage,
            backend=self._backend,
            hooks=self._hooks,
        )

    def key_for(
        self,
        template: str,
        /,
        *args: object,
        **kwargs: object,
    ) -> str:
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
        return AsyncInvalidatingDecorator(parse_tags(tags, secret=self._key_secret), self._tags, hooks=self._hooks)

    def lock(
        self,
        key: str,
        /,
        *,
        ttl: Duration,
        timeout: Duration | None = None,
        holders: int = 1,
    ) -> AsyncLock:
        """Return the lock key for a ``with`` block, held in the backend for every cache over it.

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
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> async with cache.lock("report", ttl=30):
            ...     pass
            >>> async with cache.lock("export", ttl=30, holders=3):
            ...     pass
        """
        expect_type("key", key, str)
        return AsyncLock(
            self._lock_backend,
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
        holders = parse_lock_holders(holders)

        lease = await atry_take(self._lock_backend, lock_slots(key, holders), ttl, name=key, hooks=self._hooks)
        if lease is None:
            return None
        return AsyncLock(self._lock_backend, key=key, ttl=ttl, holders=holders, lease=lease, hooks=self._hooks)

    def locked(
        self,
        *,
        ttl: Duration,
        key: str | None = None,
        timeout: Duration | None = None,
        holders: int = 1,
    ) -> AsyncLockedDecorator:
        """Run every call of a function under a lock, as ``with cache.lock(...)`` around it.

        Args:
            ttl: as in lock.
            key: a str.format template over the arguments, such as ``"report:{report_id}"``; by
                default one lock for the function.
            timeout: as in lock.
            holders: as in lock: how many calls run at once.

        Returns:
            A decorator for a function of the side of the cache.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: ttl is not positive, timeout is negative, or holders is less than 1.

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
        return AsyncLockedDecorator(
            parse_key(key, secret=self._key_secret),
            self._key_secret,
            ttl=parse_lock_ttl(ttl),
            timeout=parse_lock_timeout(timeout),
            holders=parse_lock_holders(holders),
            backend=self._lock_backend,
            hooks=self._hooks,
        )

    async def rate_limit(
        self,
        key: str,
        limit: Limit,
        /,
        *,
        cost: int = 1,
        fail_open: bool = True,
    ) -> RateLimitState | None:
        """Count a call for key in the backend, and return what is left of the limit.

        Call it before the work it guards. A failing backend lets the call through uncounted,
        returns None and goes to on_error.

        Args:
            key: what the limit counts, such as ``f"ip:{ip}"``.
            limit: the limit, such as ``SlidingWindow.per_minute(100)``.
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
            >>> from pashe.ratelimit import SlidingWindow
            >>> state = await cache.rate_limit("ip:203.0.113.7", SlidingWindow.per_minute(100))
            >>> state.remaining
            99
        """
        expect_type("key", key, str)
        expect_type("limit", limit, LIMIT)
        cost = parse_cost(limit, cost)
        expect_type("fail_open", fail_open, bool)
        return await self._limiter.count(key, limit, cost=cost, fail_open=fail_open)

    def rate_limited(self, limit: Limit, /, *, key: str | None = None) -> AsyncRateLimitedDecorator:
        """Count every call of a function with rate_limit before it runs.

        Args:
            limit: the limit, such as ``SlidingWindow.per_minute(10)``.
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
            >>> from pashe.ratelimit import SlidingWindow
            >>> @cache.rate_limited(SlidingWindow.per_minute(10), key="export:{user_id}")
            ... async def export(user_id: int) -> int:
            ...     return user_id
            >>> await export(1)
            1
        """
        expect_type("limit", limit, LIMIT)
        return AsyncRateLimitedDecorator(
            parse_key(key, secret=self._key_secret), self._key_secret, limit=limit, limiter=self._limiter
        )

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

        The cache owns what it was given, as a backend owns its client. Each part is closed even
        when one before it fails or the call is cancelled; the error of the last one that failed is raised.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> await cache.aclose()
        """
        async with contextlib.AsyncExitStack() as closing:  # run in reverse: background, backend, fallback
            closing.push_async_callback(self._fallback.aclose)
            closing.push_async_callback(self._backend.aclose)
            closing.push_async_callback(self._background.aclose)

    @override
    def __repr__(self) -> str:
        """Show the backend and the prefix of the cache."""
        backend, prefix = self._backend.backend, self._backend.prefix
        return f"{type(self).__name__}({backend!r}, prefix={prefix!r})"

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
