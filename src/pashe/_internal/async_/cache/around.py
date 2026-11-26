from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, final, override

from pashe._internal.async_.tasks import acheck_side
from pashe._internal.cache.keys import KeyBuilder, KeyTemplate, key_name
from pashe.errors import BackendError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pashe._internal.async_.cache.cache import AsyncCache
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe.hooks import Hook
    from pashe.ratelimit import Limit


class AsyncKeyedDecorator(ABC):
    """What the decorators of a lock and of a rate limit share: every call runs under its key."""

    __slots__ = ("_cache", "_key", "_key_secret")

    def __init__(
        self,
        cache: AsyncCache,
        key: KeyTemplate | None,
        key_secret: bytes | None,
    ) -> None:
        self._cache = cache
        self._key = key
        self._key_secret = key_secret  # for the default key: the name of the function

    def __call__[**P, R](self, function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """Run every call of function under its key.

        Args:
            function: of the side of the cache.

        Returns:
            function, run under its key.
        """
        acheck_side(function, "decorate")
        keys = KeyBuilder(function, self._key or KeyTemplate(key_name(function), secret=self._key_secret), ())

        @functools.wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await self._run(keys.key(args, kwargs), functools.partial(function, *args, **kwargs))

        return wrapper

    @abstractmethod
    async def _run[R](self, key: str, call: Callable[[], Awaitable[R]]) -> R:
        raise NotImplementedError


@final
class AsyncLockedDecorator(AsyncKeyedDecorator):
    """What ``@cache.locked(...)`` returns: a decorator that runs every call under the lock of its key."""

    __slots__ = ("_holders", "_timeout", "_ttl")

    def __init__(
        self,
        cache: AsyncCache,
        key: KeyTemplate | None,
        key_secret: bytes | None,
        *,
        ttl: float,
        timeout: float | None,
        holders: int,
    ) -> None:
        super().__init__(cache, key, key_secret)

        self._ttl = ttl
        self._timeout = timeout
        self._holders = holders

    @override
    async def _run[R](self, key: str, call: Callable[[], Awaitable[R]]) -> R:
        async with self._cache.lock(key, ttl=self._ttl, timeout=self._timeout, holders=self._holders):
            return await call()


@final
class AsyncRateLimitedDecorator(AsyncKeyedDecorator):
    """What ``@cache.rate_limited(...)`` returns: a decorator that counts every call before it runs."""

    __slots__ = ("_limit",)

    def __init__(
        self,
        cache: AsyncCache,
        key: KeyTemplate | None,
        key_secret: bytes | None,
        *,
        limit: Limit,
    ) -> None:
        super().__init__(cache, key, key_secret)

        self._limit = limit

    @override
    async def _run[R](self, key: str, call: Callable[[], Awaitable[R]]) -> R:
        await self._cache.rate_limit(key, self._limit)  # over the limit it raises RateLimitedError
        return await call()


@final
class AsyncInvalidatingDecorator:
    """What ``@cache.invalidates(...)`` returns: a decorator that invalidates the tags of every call after it ran, even one that raised."""

    __slots__ = ("_hooks", "_tags", "_templates")

    def __init__(
        self,
        templates: tuple[KeyTemplate, ...],
        tags: AsyncTags,
        *,
        hooks: Hook,
    ) -> None:
        self._templates = templates
        self._tags = tags
        self._hooks = hooks

    def __call__[**P, R](self, function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """Invalidate the tags of every call of function after it ran.

        Args:
            function: the write, of the side of the cache.

        Returns:
            function, invalidating its tags.
        """
        acheck_side(function, "decorate")
        keys = KeyBuilder(function, None, self._templates)

        @functools.wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tags = keys.tags(args, kwargs)
            try:
                return await function(*args, **kwargs)
            finally:  # a write that raised may have changed data all the same
                await self._invalidate(tags)

        return wrapper

    async def _invalidate(self, tags: tuple[str, ...]) -> None:
        try:
            await self._tags.invalidate(tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.INVALIDATE, ", ".join(tags), error))
