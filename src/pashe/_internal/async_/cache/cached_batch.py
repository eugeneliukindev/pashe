from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Protocol, final, override

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterable

    from pashe._internal.async_.cache.batch_cache import AsyncBatchCache, AsyncBatchFunction
    from pashe._internal.cache.keys import ItemKeys


@final
class AsyncCachedBatchFunction[K: Hashable, V]:
    """A function of a batch, ``f(items) -> {item: value}``, whose results are cached per item.

    A call reads every item in one backend call and calls the function once with the missing ones.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> cache = AsyncCache(AsyncMemoryBackend())
        >>> @cache.batch(ttl=60, key="user:{}")
        ... async def get_users(user_ids: list[int]) -> dict[int, dict[str, int]]:
        ...     return {user_id: {"id": user_id} for user_id in user_ids if user_id > 0}
        >>> await get_users([1, 2])
        {1: {'id': 1}, 2: {'id': 2}}
    """

    __slots__ = ("__dict__", "_batch_cache", "_function", "_keys")

    def __init__(
        self,
        function: AsyncBatchFunction[K, V],
        keys: ItemKeys,
        batch_cache: AsyncBatchCache[K, V],
    ) -> None:
        """Made by the batch decorator of a cache, not by hand.

        Args:
            function: the batch function whose results are cached per item.
            keys: builds the key and the tags of an item.
            batch_cache: answers the items from the backend or by calling the function.
        """
        self._function = function
        self._keys = keys
        self._batch_cache = batch_cache

        functools.update_wrapper(self, function)

    async def __call__(self, items: Iterable[K], /) -> dict[K, V]:
        """Return the results of items: cached, or loaded in one call of the function.

        Args:
            items: the items, each with a key of its own.

        Returns:
            The result of every item the function returned; items it left out are absent and
            not cached.

        Raises:
            TypeError: items is not iterable, or an item cannot be a part of a key without a template.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.batch(ttl=60, key="user:{}")
            ... async def get_users(user_ids: list[int]) -> dict[int, dict[str, int]]:
            ...     return {user_id: {"id": user_id} for user_id in user_ids if user_id > 0}
            >>> await get_users([0, 1])
            {1: {'id': 1}}
        """
        calls = {item: self._keys.key_and_tags(item) for item in items}
        return await self._batch_cache.get_or_load_many(calls, self._function)

    async def invalidate(self, item: K, /) -> bool:
        """Drop the cached result of item.

        Args:
            item: the item.

        Returns:
            Whether there was a cached result.

        Examples:
            >>> from pashe import AsyncCache
            >>> from pashe.backends import AsyncMemoryBackend
            >>> cache = AsyncCache(AsyncMemoryBackend())
            >>> @cache.batch(ttl=60, key="user:{}")
            ... async def get_users(user_ids: list[int]) -> dict[int, dict[str, int]]:
            ...     return {user_id: {"id": user_id} for user_id in user_ids if user_id > 0}
            >>> await get_users([1])
            {1: {'id': 1}}
            >>> await get_users.invalidate(1)
            True
        """
        return await self._batch_cache.delete(self._keys.key(item))

    @override
    def __repr__(self) -> str:
        """Show the batch function, by its qualified name."""
        return f"{type(self).__name__}({getattr(self._function, '__qualname__', self._function)})"


class AsyncCachedBatchFunctionDecorator(Protocol):
    """What ``@cache.batch(...)`` returns: a decorator that caches every item of a batch function on its own."""

    def __call__[K: Hashable, V](self, function: AsyncBatchFunction[K, V], /) -> AsyncCachedBatchFunction[K, V]:
        """Cache the items function loads: it takes a list of items and returns a dict of those it found."""
        ...
