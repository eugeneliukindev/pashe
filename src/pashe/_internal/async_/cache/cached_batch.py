from __future__ import annotations

import functools
from typing import TYPE_CHECKING, final, override

from pashe._internal.async_.cache.batch_cache import AsyncBatchCache
from pashe._internal.async_.tasks import aexpect_side
from pashe._internal.cache.call import CallReporter
from pashe._internal.cache.entry import EntryFormat
from pashe._internal.cache.keys import ItemKeys, qualified_name
from pashe._internal.cache.value_types import item_type

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterable

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.batch_cache import AsyncBatchFunction
    from pashe._internal.async_.cache.storage import AsyncStorage
    from pashe._internal.cache.keys import KeyTemplate
    from pashe._internal.cache.policy import Policy
    from pashe.codecs import Codec
    from pashe.compressors import Compressor
    from pashe.hooks import Hook


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


@final
class AsyncCachedBatchFunctionDecorator:
    """What ``@cache.batch(...)`` returns: a decorator that caches every item of a batch function on its own."""

    __slots__ = (
        "_backend",
        "_codec",
        "_compressor",
        "_hooks",
        "_key_template",
        "_policy",
        "_storage",
        "_tag_templates",
    )

    def __init__(
        self,
        policy: Policy,
        /,
        *,
        key_template: KeyTemplate | None,
        tag_templates: tuple[KeyTemplate, ...],
        codec: Codec,
        compressor: Compressor,
        storage: AsyncStorage,
        backend: AsyncPrefixedBackend,
        hooks: Hook,
    ) -> None:
        self._policy = policy
        self._key_template = key_template
        self._tag_templates = tag_templates

        self._codec = codec
        self._compressor = compressor
        self._storage = storage
        self._backend = backend  # for the full keys the hooks are told
        self._hooks = hooks

    def __call__[K: Hashable, V](self, function: AsyncBatchFunction[K, V]) -> AsyncCachedBatchFunction[K, V]:
        """Cache the items function loads.

        Args:
            function: takes a list of items and returns a dict of the ones it found.

        Returns:
            The cached batch function.
        """
        aexpect_side(function, "cache")
        entry_format = EntryFormat(
            self._policy, item_type(function), codec=self._codec, compressor=self._compressor, hooks=self._hooks
        )
        keys = ItemKeys(function, self._key_template, self._tag_templates)

        batch_cache = AsyncBatchCache[K, V](
            self._policy,
            storage=self._storage,
            entry_format=entry_format,
            reporter=CallReporter(
                qualified_name(function), self._backend.full_key, hooks=self._hooks, clock=self._policy.clock
            ),
            hooks=self._hooks,
        )
        return AsyncCachedBatchFunction(function, keys, batch_cache)
