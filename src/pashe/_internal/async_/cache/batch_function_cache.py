from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, final

from pashe._internal.async_.tasks import AsyncConcurrencyLimit
from pashe._internal.cache.call import Answer, CallReporter, CallState, in_no_cache, timed
from pashe.errors import BackendError
from pashe.hooks import CacheStatus, Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Hashable, Mapping

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.fallback import AsyncFallbackStore
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe._internal.cache.entry import Stored
    from pashe._internal.cache.entry_codec import EntryCodec
    from pashe._internal.cache.keys import KeyAndTags
    from pashe._internal.cache.policy import Policy
    from pashe.hooks import Hook

type AsyncBatchFunction[K: Hashable, V] = Callable[[list[K]], Awaitable[Mapping[K, V]]]
type _Store = Callable[[dict[str, Stored]], Awaitable[None]]  # keeps what a batch loaded, by key


@final
@dataclass(slots=True)
class _Item[K: Hashable]:
    # one item of a batch call, from the read to the store
    item: K
    state: CallState  # its key and tags, and the generations of the tags once read
    stored: Stored | None = None  # what the backend kept past its TTL: it may answer if the load fails
    answered: bool = False
    value: object = None  # decoded as the value type, once answered

    def answer(self, value: object) -> None:
        self.answered = True
        self.value = value


@final
class AsyncBatchFunctionCache[K: Hashable, V]:
    # The cache of one batch function: reads every item at once, loads the missing ones in one call.
    __slots__ = ("_backend", "_codec", "_concurrency", "_fallback", "_hooks", "_policy", "_reporter", "_tags")

    def __init__(
        self,
        policy: Policy,
        *,
        codec: EntryCodec,
        reporter: CallReporter,
        hooks: Hook,
        backend: AsyncPrefixedBackend,
        tags: AsyncTags,
        fallback: AsyncFallbackStore,
    ) -> None:
        self._policy = policy
        self._codec = codec
        self._reporter = reporter
        self._hooks = hooks
        self._backend = backend
        self._tags = tags
        self._fallback = fallback

        self._concurrency = AsyncConcurrencyLimit(policy.stampede.max_loads)

    async def get_or_load_many(self, calls: Mapping[K, KeyAndTags], load: AsyncBatchFunction[K, V]) -> dict[K, V]:
        items = [_Item(item, CallState(key, tags)) for item, (key, tags) in calls.items()]
        store: _Store = self._store
        if in_no_cache():  # every item loads, and is stored for the calls after it
            await self._read_generations(items)
        else:
            try:
                await self._read(items)
            except BackendError as error:
                self._hooks.on_error(Failure(Operation.GET_MANY, "", error))
                await self._read_fallback(items)
                store = self._store_in_fallback
        await store(await self._load([item for item in items if not item.answered], load))
        return {item.item: item.value for item in items if item.answered}  # type: ignore[misc]  # decoded as the value type

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)

    async def _read(self, items: list[_Item[K]]) -> None:
        read = await self._tags.read_many([(item.state.key, item.state.tags) for item in items])
        for item, (raw, generations) in zip(items, read, strict=True):
            item.state.tag_generations = generations  # what a load after it stores with, as in a cached function
            self._answer(item, self._codec.decode(item.state.key, raw, generations), CacheStatus.HIT)

    async def _read_fallback(self, items: list[_Item[K]]) -> None:
        for item in items:
            kept = await self._fallback.get(item.state.key)  # noqa: WPS476 - memory, nothing to win at once
            self._answer(item, self._codec.decode(item.state.key, kept, ()), CacheStatus.FALLBACK)  # it keeps no tags

    async def _read_generations(self, items: list[_Item[K]]) -> None:
        # the generations of the tags alone, for what no_cache loads and stores
        try:
            read = await self._tags.read_many([(item.state.key, item.state.tags) for item in items])
        except BackendError as error:  # stored untagged, each is a miss for the calls after it
            self._hooks.on_error(Failure(Operation.READ_TAGS, "", error))
            return
        for item, (_, generations) in zip(items, read, strict=True):
            item.state.tag_generations = generations

    def _answer(self, item: _Item[K], stored: Stored | None, status: CacheStatus) -> None:
        answer = self._policy.answer_for(stored)
        if answer is not None and answer.status is not CacheStatus.NOT_FOUND:  # a batch keeps no "not found"
            item.answer(answer.value)
            self._reporter.report(item.state.key, status, stale_at=answer.stale_at)
        elif stored is not None and not stored.entry.negative:
            item.stored = stored

    async def _load(self, missing: list[_Item[K]], load: AsyncBatchFunction[K, V]) -> dict[str, Stored]:
        # loads the missing items in one call; what it returns is to be stored, by key
        if not missing:
            return {}

        batch = CallState("")
        try:
            async with self._concurrency.slot(has_stale_answer=False):
                with timed(batch):
                    loaded = await load([item.item for item in missing])
        except Exception as error:
            if not self._answer_stale(missing, error):
                raise
            return {}
        return self._take(missing, loaded, batch.load_seconds)

    def _take(
        self,
        missing: list[_Item[K]],
        loaded: Mapping[K, V],
        load_seconds: float,
    ) -> dict[str, Stored]:
        # answers the items with what the batch loaded; what is to be stored, by key
        to_store: dict[str, Stored] = {}
        for item in missing:
            state = replace(item.state, load_seconds=load_seconds)  # every item took the whole batch
            if item.item not in loaded:  # the function left it out: absent from the result, not stored
                self._reporter.report(state.key, CacheStatus.MISS, load_seconds=state.load_seconds)
                continue
            stored = self._codec.encode_loaded(state, loaded[item.item])
            item.answer(loaded[item.item] if stored is None else stored.value)
            self._reporter.report(
                state.key, CacheStatus.MISS, load_seconds=state.load_seconds, stale_at=stored and stored.entry.stale_at
            )
            if stored is not None:
                to_store[state.key] = stored
        return to_store

    def _answer_stale(self, missing: list[_Item[K]], error: Exception) -> bool:
        # The load failed: stale results answer, if each item it was for has one in Stale.if_error;
        # the items are one call, so with one of them missing the error goes to the caller.
        answers: list[Answer] = []
        for item in missing:
            answer = None if item.stored is None else self._policy.stale_answer(item.state, item.stored, error)
            if answer is None:
                return False
            answers.append(answer)

        self._hooks.on_error(Failure(Operation.LOAD, "", error))
        for item, stale in zip(missing, answers, strict=True):
            item.answer(stale.value)
            self._reporter.report(item.state.key, stale.status, stale_at=stale.stale_at)
        return True

    async def _store(self, to_store: dict[str, Stored]) -> None:
        if not to_store:
            return
        raws = {key: stored.raw for key, stored in to_store.items()}
        try:
            await self._backend.set_many(raws, ttl=max(map(self._policy.storage_lifetime, to_store.values())))
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.SET_MANY, "", error))
            await self._store_in_fallback(to_store)

    async def _store_in_fallback(self, to_store: dict[str, Stored]) -> None:
        for key, stored in to_store.items():
            await self._fallback.set(key, stored)  # noqa: WPS476 - memory, nothing to win at once
