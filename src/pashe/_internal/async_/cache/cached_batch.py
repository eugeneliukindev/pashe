from __future__ import annotations

import functools
from typing import TYPE_CHECKING, final

from pashe._internal.async_.cache.batch_function_cache import AsyncBatchFunctionCache
from pashe._internal.async_.tasks import acheck_side
from pashe._internal.cache.call import CallReporter
from pashe._internal.cache.entry import EntryFormat
from pashe._internal.cache.entry_codec import EntryCodec
from pashe._internal.cache.keys import item_key, key_name, qualified_name
from pashe._internal.cache.value_types import item_type

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterable

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.batch_function_cache import AsyncBatchFunction
    from pashe._internal.async_.cache.fallback import AsyncFallbackStore
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe._internal.cache.entry import Serializer
    from pashe._internal.cache.keys import KeyTemplate
    from pashe._internal.cache.policy import Policy
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

    __slots__ = ("__dict__", "_batch", "_function", "_key", "_name", "_tags")

    def __init__(
        self,
        function: AsyncBatchFunction[K, V],
        batch: AsyncBatchFunctionCache[K, V],
        *,
        key: KeyTemplate | None,
        tags: tuple[KeyTemplate, ...],
    ) -> None:
        """Made by the batch decorator of a cache, not by hand.

        Args:
            function: the batch function whose results are cached per item.
            batch: answers the items from the backend or by calling the function.
            key: the template of the key of an item.
            tags: the templates of the tags of an item.
        """
        self._function = function
        self._batch = batch
        self._key = key
        self._tags = tags

        self._name = key_name(function) if key is None else qualified_name(function)
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
        calls = {
            item: (item_key(self._name, self._key, item), tuple(tag.render((item,), {}) for tag in self._tags))
            for item in items
        }
        return await self._batch.get_or_load_many(calls, self._function)

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
        return await self._batch.delete(item_key(self._name, self._key, item))


@final
class AsyncCachedBatchFunctionDecorator:
    """What ``@cache.batch(...)`` returns: a decorator that caches every item of a batch function on its own."""

    __slots__ = ("_backend", "_fallback", "_hooks", "_key", "_policy", "_serializer", "_tag_store", "_tags")

    def __init__(
        self,
        policy: Policy,
        /,
        *,
        key: KeyTemplate | None,
        tags: tuple[KeyTemplate, ...],
        serializer: Serializer,
        backend: AsyncPrefixedBackend,
        tag_store: AsyncTags,
        fallback: AsyncFallbackStore,
        hooks: Hook,
    ) -> None:
        self._policy = policy
        self._key = key
        self._tags = tags

        self._serializer = serializer
        self._backend = backend
        self._tag_store = tag_store
        self._fallback = fallback
        self._hooks = hooks

    def __call__[K: Hashable, V](self, function: AsyncBatchFunction[K, V]) -> AsyncCachedBatchFunction[K, V]:
        """Cache the items function loads.

        Args:
            function: takes a list of items and returns a dict of the ones it found.

        Returns:
            The cached batch function.
        """
        acheck_side(function, "cache")
        value_type = item_type(function)
        self._serializer.check(value_type)  # a type the codec gives back as another one is refused here
        batch = AsyncBatchFunctionCache[K, V](
            self._policy,
            codec=EntryCodec(self._policy, EntryFormat(self._serializer, value_type), self._hooks),
            reporter=CallReporter(
                qualified_name(function), self._backend.full_key, hooks=self._hooks, clock=self._policy.clock
            ),
            hooks=self._hooks,
            backend=self._backend,
            tags=self._tag_store,
            fallback=self._fallback,
        )
        return AsyncCachedBatchFunction(function, batch, key=self._key, tags=self._tags)
