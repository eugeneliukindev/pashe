from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, final

from pashe._internal.async_.tasks import AsyncConcurrencyLimit
from pashe._internal.cache.call import CallState, in_no_cache, timed
from pashe.errors import BackendError
from pashe.hooks import CacheStatus, Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Hashable, Mapping, Sequence

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.fallback import AsyncFallbackStore
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe._internal.cache.call import Answer, CallReporter
    from pashe._internal.cache.entry import Generations, Stored
    from pashe._internal.cache.entry_codec import EntryCodec
    from pashe._internal.cache.policy import Policy
    from pashe.hooks import Hook

type _States[K: Hashable] = dict[K, CallState]
type _ToStore[K: Hashable] = dict[K, Stored]
type _Found[K: Hashable] = dict[K, object]  # values decoded as the value type
type _Missing[K: Hashable] = dict[K, Stored | None]  # the items to load, with the stale entry each may answer with
type BatchCalls[K: Hashable] = Mapping[K, tuple[str, tuple[str, ...]]]  # the key and the tags of every item
type AsyncBatchFunction[K: Hashable, V] = Callable[[list[K]], Awaitable[Mapping[K, V]]]


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

    async def get_or_load_many(self, calls: BatchCalls[K], load: AsyncBatchFunction[K, V]) -> dict[K, V]:
        states = {item: CallState(key, tags) for item, (key, tags) in calls.items()}
        if in_no_cache():  # every item loads, and is stored for the calls after it
            await self._read_generations(states)
            found: _Found[K] = {}
            await self._store_all(states, await self._load(states, found, missing=dict.fromkeys(states), load=load))
            return {item: found[item] for item in states if item in found}  # type: ignore[misc]  # decoded as the value type
        try:
            read = await self._tags.read_many([(state.key, state.tags) for state in states.values()])
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET_MANY, "", error))
            return await self._serve_from_fallback(states, load)

        found, missing = self._sort(states, self._decode(states, read), CacheStatus.HIT)
        await self._store_all(states, await self._load(states, found, missing=missing, load=load))
        return {item: found[item] for item in states if item in found}  # type: ignore[misc]  # decoded as the value type

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)

    def _decode(self, states: _States[K], read: Sequence[tuple[bytes | None, Generations]]) -> list[Stored | None]:
        stored: list[Stored | None] = []
        for state, (raw, generations) in zip(states.values(), read, strict=True):
            state.tag_generations = generations  # what a load after it stores with, as in a cached function
            stored.append(self._codec.decode(state.key, raw, generations))
        return stored

    async def _serve_from_fallback(self, states: _States[K], load: AsyncBatchFunction[K, V]) -> dict[K, V]:
        stored = [
            self._codec.decode(state.key, await self._fallback.get(state.key), ())  # noqa: WPS476 - memory, nothing to win
            for state in states.values()
        ]
        found, missing = self._sort(states, stored, CacheStatus.FALLBACK)
        await self._store_all_in_fallback(states, await self._load(states, found, missing=missing, load=load))
        return {item: found[item] for item in states if item in found}  # type: ignore[misc]  # decoded as the value type

    async def _read_generations(self, states: _States[K]) -> None:
        # the generations of the tags alone, for what no_cache loads and stores
        try:
            read = await self._tags.read_many([(state.key, state.tags) for state in states.values()])
        except BackendError as error:  # stored untagged, each is a miss for the calls after it
            self._hooks.on_error(Failure(Operation.READ_TAGS, "", error))
            return
        for state, (_, generations) in zip(states.values(), read, strict=True):
            state.tag_generations = generations

    def _sort(
        self,
        states: _States[K],
        stored: Sequence[Stored | None],
        status: CacheStatus,
    ) -> tuple[_Found[K], _Missing[K]]:
        found: _Found[K] = {}
        missing: _Missing[K] = {}
        for (item, state), entry in zip(states.items(), stored, strict=True):
            answer = self._policy.answer_for(entry)
            if answer is not None and answer.status is not CacheStatus.NOT_FOUND:  # a batch keeps no "not found"
                found[item] = answer.value
                self._reporter.report(state.key, status, stale_at=answer.stale_at)
            else:
                missing[item] = None if entry is None or entry.entry.negative else entry
        return found, missing

    async def _load(
        self,
        states: _States[K],
        found: _Found[K],
        *,
        missing: _Missing[K],
        load: AsyncBatchFunction[K, V],
    ) -> _ToStore[K]:
        if not missing:
            return {}

        batch = CallState("")
        try:
            loaded = await self._run(batch, list(missing), load)
        except Exception as error:
            if not self._answer_stale(states, found, missing=missing, error=error):
                raise
            return {}
        return self._encode_loaded(states, found, missing=missing, loaded=loaded, load_seconds=batch.load_seconds)

    async def _run(
        self,
        batch: CallState,
        items: list[K],
        load: AsyncBatchFunction[K, V],
    ) -> Mapping[K, V]:
        async with self._concurrency.slot(has_stale_answer=False):
            with timed(batch):
                return await load(items)

    def _encode_loaded(
        self,
        states: _States[K],
        found: _Found[K],
        *,
        missing: _Missing[K],
        loaded: Mapping[K, V],
        load_seconds: float,
    ) -> _ToStore[K]:
        to_store: _ToStore[K] = {}
        for item in missing:
            state = replace(states[item], load_seconds=load_seconds)  # every item took the whole batch
            if item not in loaded:  # the function left it out: absent from the result, not stored
                self._reporter.report(state.key, CacheStatus.MISS, load_seconds=state.load_seconds)
                continue
            stored = self._codec.encode_loaded(state, loaded[item])
            found[item] = loaded[item] if stored is None else stored.value
            self._reporter.report(
                state.key,
                CacheStatus.MISS,
                load_seconds=state.load_seconds,
                stale_at=stored and stored.entry.stale_at,
            )
            if stored is not None:
                to_store[item] = stored

        return to_store

    def _answer_stale(
        self,
        states: _States[K],
        found: _Found[K],
        *,
        missing: _Missing[K],
        error: Exception,
    ) -> bool:
        # The load failed: stale results answer, if each item it was for has one in Stale.if_error;
        # the items are one call, so with one of them missing the error goes to the caller.
        answers: dict[K, Answer] = {}
        for item, stored in missing.items():
            answer = None
            if stored is not None:
                within = self._policy.stale_windows(stored).within_if_error
                answer = self._policy.stale_answer(
                    states[item], stored, error, within_if_error=within, within_if_slow=False
                )
            if answer is None:
                return False
            answers[item] = answer

        self._hooks.on_error(Failure(Operation.LOAD, "", error))
        for item, answer in answers.items():
            found[item] = answer.value
            self._reporter.report(states[item].key, answer.status, stale_at=answer.stale_at)
        return True

    async def _store_all(self, states: _States[K], to_store: _ToStore[K]) -> None:
        if not to_store:
            return
        raws = {states[item].key: stored.raw for item, stored in to_store.items()}
        try:
            await self._backend.set_many(raws, ttl=max(map(self._policy.storage_lifetime, to_store.values())))
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.SET_MANY, "", error))
            await self._store_all_in_fallback(states, to_store)

    async def _store_all_in_fallback(self, states: _States[K], to_store: _ToStore[K]) -> None:
        for item, stored in to_store.items():
            await self._fallback.set(states[item].key, stored)  # noqa: WPS476 - memory, nothing to win at once
