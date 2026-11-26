from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Concatenate, Protocol, Self, final, overload, override

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from pashe._internal.async_.cache.function_cache import AsyncFunctionCache, AsyncLoad
    from pashe._internal.cache.keys import CallKeys


class AsyncCachedValue[**P, R]:
    """A place in the cache for values of yours, found by the arguments of a function that never runs.

    ``@cache.value(...)`` makes it of a function with no body to run: its parameters fill the
    templates of the key and the tags, and its return annotation says what a value decodes as.
    A method can be one too; ``self`` and ``cls`` are left out of the default key.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> cache = AsyncCache(AsyncMemoryBackend())
        >>> @cache.value(ttl=600, key="otp:{email}")
        ... async def login_code(email: str) -> str:
        ...     raise NotImplementedError  # the function of a value never runs
        >>> await login_code.set("482913", "ada@example.com")
        >>> await login_code.get("ada@example.com")
        '482913'
    """

    __slots__ = ("__dict__", "_function", "_function_cache", "_instance", "_keys")

    def __init__(
        self,
        function: Callable[P, Awaitable[R]],
        keys: CallKeys,
        function_cache: AsyncFunctionCache[R],
        *,
        instance: object | None = None,
    ) -> None:
        """Made by the decorators of a cache, not by hand.

        Args:
            function: the function whose arguments find a value.
            keys: builds the key and the tags of a call.
            function_cache: reads and writes the entries in the backend.
            instance: the instance a method was read from.
        """
        self._function = function
        self._keys = keys
        self._function_cache = function_cache
        self._instance = instance  # the instance a method was read from
        functools.update_wrapper(self, function)  # type: ignore[arg-type]  # typeshed asks a callable: its names and docs are copied

    async def get(self, *args: P.args, **kwargs: P.kwargs) -> R | None:
        """Return the fresh value of the call, loading nothing.

        Args:
            *args: the arguments of the function.
            **kwargs: the keyword arguments of the function.

        Returns:
            The value, decoded as the return annotation of the function; None if none is fresh.

        Raises:
            BackendError: the backend failed: there is no load to answer with.
            NotFoundError: a cached function keeps a "not found" for the call, as Negative says.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.value(ttl=600, key="otp:{email}")
            ... async def login_code(email: str) -> str:
            ...     raise NotImplementedError  # the function of a value never runs
            >>> await login_code.get("ada@example.com") is None
            True
        """
        key, tags, _ = self._bind(args, kwargs)
        return await self._function_cache.get(key, tags)

    async def set(
        self,
        value: R,
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """Store value as the value of the call, with the TTL and the tags of the decorator.

        A value Store.when of a cached function rejects deletes the stored one instead.

        Args:
            value: the value to store.
            *args: the arguments of the function.
            **kwargs: the keyword arguments of the function.

        Raises:
            BackendError: the backend failed, and nothing is stored.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.value(ttl=600, key="otp:{email}")
            ... async def login_code(email: str) -> str:
            ...     raise NotImplementedError  # the function of a value never runs
            >>> await login_code.set("482913", "ada@example.com")
        """
        key, tags, _ = self._bind(args, kwargs)
        await self._function_cache.set(key, tags, value)

    async def invalidate(self, *args: P.args, **kwargs: P.kwargs) -> bool:
        """Drop the stored value of the call.

        Args:
            *args: the arguments of the function.
            **kwargs: the keyword arguments of the function.

        Returns:
            Whether there was a stored value.

        Raises:
            BackendError: the backend failed.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.value(ttl=600, key="otp:{email}")
            ... async def login_code(email: str) -> str:
            ...     raise NotImplementedError  # the function of a value never runs
            >>> await login_code.set("482913", "ada@example.com")
            >>> await login_code.invalidate("ada@example.com"), await login_code.invalidate("ada@example.com")
            (True, False)
        """
        return await self._function_cache.delete(self._bind(args, kwargs)[0])

    @override
    def __repr__(self) -> str:
        """Show the function, by its qualified name."""
        return f"{type(self).__name__}({getattr(self._function, '__qualname__', self._function)})"

    @overload
    def __get__(self, instance: None, owner: type[object]) -> Self: ...

    @overload
    def __get__[S, **Q](
        self: AsyncCachedValue[Concatenate[S, Q], R],
        instance: S,
        owner: type[object],
    ) -> AsyncCachedValue[Q, R]: ...

    def __get__(self, instance: object, owner: type[object]) -> object:
        """Bind a method to its instance, as a function would be."""
        if instance is None:
            return self
        return type(self)(self._function, self._keys, self._function_cache, instance=instance)

    def _bind(
        self,
        args: Sequence[object],
        kwargs: Mapping[str, object],
    ) -> tuple[str, tuple[str, ...], AsyncLoad[R]]:
        full = tuple(args) if self._instance is None else (self._instance, *args)
        function: Callable[..., Awaitable[R]] = self._function  # bound to the instance of a method
        load = functools.partial(function, *full, **kwargs)
        key, tags = self._keys.key_and_tags(full, kwargs)
        return key, tags, load


@final
class AsyncCachedFunction[**P, R](AsyncCachedValue[P, R]):
    """A function whose results are cached: call it as the function.

    It is the AsyncCachedValue of a function that loads: ``get``, ``set`` and ``invalidate`` find the entry by the
    same arguments, and ``refresh`` loads it again. A method can be cached too; ``self`` and
    ``cls`` are left out of the default key, so name the instance in the template when the
    result depends on it, such as ``"user:{self.id}"``.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> cache = AsyncCache(AsyncMemoryBackend())
        >>> @cache(ttl=60, key="user:{user_id}")
        ... async def get_user(user_id: int) -> dict[str, int]:
        ...     return {"id": user_id}
        >>> await get_user(1)
        {'id': 1}
        >>> await get_user.invalidate(1)
        True
    """

    __slots__ = ()

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Return the cached result of the call, or call the function and cache what it returns.

        Args:
            *args: the arguments of the function.
            **kwargs: the keyword arguments of the function.

        Returns:
            The result, decoded as the return annotation of the function.

        Raises:
            NotFoundError: the function raised one of Negative.on, now or when it was cached.
            TypeError: the arguments do not fit the function, or one cannot be a part of a key
                without a template.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache(ttl=60, key="user:{user_id}")
            ... async def get_user(user_id: int) -> dict[str, int]:
            ...     return {"id": user_id}
            >>> await get_user(1)
            {'id': 1}
        """
        return await self._function_cache.get_or_load(*self._bind(args, kwargs))

    async def refresh(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the function and cache its result whatever is cached, as after the data changed.

        An error of the function leaves the cached result alone; a result the policy does not store, such
        as one Store.when rejects, deletes it.

        Args:
            *args: the arguments of the function.
            **kwargs: the keyword arguments of the function.

        Returns:
            The new result.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache(ttl=60, key="user:{user_id}")
            ... async def get_user(user_id: int) -> dict[str, int]:
            ...     return {"id": user_id}
            >>> await get_user.refresh(1)
            {'id': 1}
        """
        return await self._function_cache.refresh(*self._bind(args, kwargs))

    @overload
    def __get__(self, instance: None, owner: type[object]) -> Self: ...

    @overload
    def __get__[S, **Q](
        self: AsyncCachedFunction[Concatenate[S, Q], R],
        instance: S,
        owner: type[object],
    ) -> AsyncCachedFunction[Q, R]: ...

    @override
    def __get__(self, instance: object, owner: type[object]) -> object:
        """Bind a cached method to its instance, as a function would be."""
        if instance is None:
            return self
        return AsyncCachedFunction(self._function, self._keys, self._function_cache, instance=instance)


class AsyncCachedFunctionDecorator(Protocol):
    """What ``@cache(...)`` returns: a decorator that caches the results of a function."""

    def __call__[**Q, T](self, function: Callable[Q, Awaitable[T]], /) -> AsyncCachedFunction[Q, T]:
        """Cache the results of function, of the side of the cache."""
        ...


class AsyncCachedValueDecorator(Protocol):
    """What ``@cache.value(...)`` returns: a decorator that makes a value set by hand of a function."""

    def __call__[**Q, T](self, function: Callable[Q, Awaitable[T]], /) -> AsyncCachedValue[Q, T]:
        """Make function a value: its signature gives the key, its body never runs."""
        ...
