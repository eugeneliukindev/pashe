from __future__ import annotations

import functools
from typing import TYPE_CHECKING, final

from pashe._internal.async_.cache.revalidation import AsyncRevalidation
from pashe._internal.async_.locks.locking import aacquire, arelease
from pashe._internal.async_.tasks import AsyncConcurrencyLimit, AsyncSingleFlight
from pashe._internal.cache.call import Answer, CallState, in_no_cache, timed
from pashe._internal.cache.keys import KeyPrefix
from pashe.errors import BackendError, NotFoundError
from pashe.hooks import CacheStatus, Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.fallback import AsyncFallbackStore
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe._internal.async_.tasks import AsyncBackgroundTasks
    from pashe._internal.cache.call import CallReporter
    from pashe._internal.cache.entry import Stored
    from pashe._internal.cache.entry_codec import EntryCodec
    from pashe._internal.cache.policy import Policy
    from pashe.hooks import Hook

type AsyncLoad[V] = Callable[[], Awaitable[V]]  # a call of the cached function with its arguments, run on a miss


@final
class AsyncFunctionCache[V]:
    # The cache of one function: reads an entry, answers from it, or loads and stores. Its policy
    # decides, its codec encodes, and it tells the hooks of what it works around.
    __slots__ = (
        "_backend",
        "_changes",
        "_codec",
        "_concurrency",
        "_fallback",
        "_hooks",
        "_policy",
        "_reporter",
        "_revalidation",
        "_single_flight",
        "_tags",
    )

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
        background: AsyncBackgroundTasks,
    ) -> None:
        self._policy = policy
        self._codec = codec
        self._reporter = reporter
        self._hooks = hooks

        self._backend = backend
        self._tags = tags
        self._fallback = fallback

        # the sets and deletes by hand in this process: a load that started before one stores
        # nothing, and is shared with no call after it
        self._changes = 0
        self._single_flight = AsyncSingleFlight()
        self._revalidation = AsyncRevalidation(
            backend=backend, background=background, hooks=hooks, slow_after=policy.stale.slow_after
        )
        self._concurrency = AsyncConcurrencyLimit(policy.stampede.max_concurrent_loads)

    async def get_or_load(
        self,
        key: str,
        tags: tuple[str, ...],
        load: AsyncLoad[V],
    ) -> V:
        state = CallState(key, tags, changes_at_start=self._changes)
        try:
            if in_no_cache():  # it shares no answer: another call may answer from the backend
                answer = await self._bypass(state, load)
            elif self._policy.stampede.single_flight:
                flight_key = (
                    key,
                    self._tags.invalidation_count,
                    self._changes,
                )  # no load started before a change is shared
                answer = await self._single_flight.share(flight_key, functools.partial(self._serve, state, load))
            else:
                answer = await self._serve(state, load)
        except Exception:
            self._reporter.report(key, CacheStatus.MISS, load_seconds=state.load_seconds)
            raise
        return self._result(key, answer)

    async def refresh(
        self,
        key: str,
        tags: tuple[str, ...],
        load: AsyncLoad[V],
    ) -> V:
        state = CallState(key, tags)
        try:
            state.tag_generations = await self._tags.generations(tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.READ_TAGS, key, error))
            value = await self._run(state, load)
            await self._fallback.set(key, self._codec.encode_loaded(state, value))
            return value

        value = await self._run(state, load)
        stored = self._codec.encode_loaded(state, value)
        if stored is None:
            await self._backend.delete(key)  # the old result must not answer after a refresh
            return value
        await self._store(state, stored)
        return stored.value  # type: ignore[return-value]  # decoded as the return type

    async def get(self, key: str, tags: tuple[str, ...]) -> V | None:
        # The fresh result alone, loading nothing: a failing backend raises, as there is no load to answer with.
        if in_no_cache():
            self._reporter.report(key, CacheStatus.MISS)
            return None
        _, answer = await self._read(CallState(key, tags))
        if answer is None or answer.status is CacheStatus.STALE_WHILE_REVALIDATE:
            self._reporter.report(key, CacheStatus.MISS)
            return None
        return self._result(key, answer)

    async def set(
        self,
        key: str,
        tags: tuple[str, ...],
        value: V,
    ) -> None:
        self._changes += 1  # before the write: a load that ends after it must not overwrite it
        state = CallState(key, tags, await self._tags.generations(tags))
        stored = self._codec.encode(state, value)
        if stored is None:
            await self._backend.delete(key)
        else:
            await self._backend.set(key, stored.raw, ttl=self._policy.storage_lifetime(stored))

    async def delete(self, key: str) -> bool:
        self._changes += 1  # before the delete, as in set
        return await self._backend.delete(key)

    def _result(self, key: str, answer: Answer) -> V:
        self._reporter.report(key, answer.status, load_seconds=answer.load_seconds, stale_at=answer.stale_at)
        if answer.status is CacheStatus.NOT_FOUND:
            raise NotFoundError(key)  # kept by an earlier call, as Negative says
        return answer.value  # type: ignore[return-value]  # decoded as the return type

    async def _bypass(self, state: CallState, load: AsyncLoad[V]) -> Answer:
        # no stored result answers: load, and store for the calls after it
        try:
            state.tag_generations = await self._tags.generations(state.tags)
        except BackendError as error:  # stored untagged, it is a miss for the calls after it
            self._hooks.on_error(Failure(Operation.READ_TAGS, state.key, error))
        return await self._load_and_store(state, load)

    async def _serve(self, state: CallState, load: AsyncLoad[V]) -> Answer:
        try:
            stored, answer = await self._read(state)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET, state.key, error))
            return await self._serve_from_fallback(state, load)
        if answer is not None:
            if self._policy.should_revalidate(answer):
                await self._revalidation.start(state, functools.partial(self._load_and_store, load=load))
            return answer

        if stored is not None and not stored.entry.negative:
            return await self._serve_stale_or_load(state, stored, load)
        if self._policy.stampede.lock_for > 0:
            return await self._load_under_lock(state, load)
        return await self._load_and_store(state, load)

    async def _read(self, state: CallState) -> tuple[Stored | None, Answer | None]:
        # The entry and how it answers. A load after it stores with the generations read here, so
        # a tag invalidated during the load makes what it stores a miss.
        raw, generations = await self._tags.read(state.key, state.tags)
        state.tag_generations = generations
        stored = self._codec.decode(state.key, raw, generations)
        return stored, self._policy.answer_for(stored)

    async def _run(self, state: CallState, load: AsyncLoad[V]) -> V:
        async with self._concurrency.slot(has_stale_answer=state.has_stale_answer):
            with timed(state):
                return await load()

    async def _load_and_store(self, state: CallState, load: AsyncLoad[V]) -> Answer:
        try:
            value = await self._run(state, load)
        except Exception as error:
            if not self._policy.is_negative(error):
                raise
            stored = self._codec.encode_negative(state)
            if stored is not None:
                await self._store(state, stored)
            raise NotFoundError(state.key) from error

        stored = self._codec.encode_loaded(state, value)
        if stored is None:
            return Answer(value, CacheStatus.MISS, state.load_seconds)
        await self._store(state, stored)
        return Answer(stored.value, CacheStatus.MISS, state.load_seconds, stored.entry.stale_at)

    async def _store(self, state: CallState, stored: Stored) -> None:
        if state.changes_at_start != self._changes:  # set or deleted by hand while it loaded: what it loaded is old
            return
        try:
            await self._backend.set(state.key, stored.raw, ttl=self._policy.storage_lifetime(stored))
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.SET, state.key, error))
            await self._fallback.set(state.key, stored)  # kept in the fallback while the backend fails

    async def _load_under_lock(self, state: CallState, load: AsyncLoad[V]) -> Answer:
        lock_key = KeyPrefix.STAMPEDE_LOCK + state.key
        try:
            owner = await aacquire(self._backend, lock_key, self._policy.stampede.lock_for)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.STAMPEDE_LOCK, state.key, error))
            return await self._load_and_store(state, load)
        try:
            return await self._read_after_lock(state) or await self._load_and_store(state, load)
        finally:
            await arelease(self._backend, lock_key, owner, hooks=self._hooks)

    async def _read_after_lock(self, state: CallState) -> Answer | None:
        try:
            _, answer = await self._read(state)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET, state.key, error))
            return None
        if answer is None or answer.status is CacheStatus.NOT_FOUND:
            return answer  # the load before this one kept a "not found"
        return Answer(answer.value, CacheStatus.HIT, stale_at=answer.stale_at)

    async def _serve_stale_or_load(
        self,
        state: CallState,
        stored: Stored,
        load: AsyncLoad[V],
    ) -> Answer:
        if_error, if_slow = self._policy.stale_windows(stored)
        state.has_stale_answer = if_error or if_slow
        try:
            if if_slow:
                loaded = await self._revalidation.wait_at_most_slow_after(
                    state, functools.partial(self._load_and_store, load=load)
                )
            else:
                loaded = await self._load_and_store(state, load)
        except Exception as error:
            stale = self._policy.stale_answer(state, stored, error, within_if_error=if_error, within_if_slow=if_slow)
            if stale is None:
                raise
            self._hooks.on_error(Failure(Operation.LOAD, state.key, error))
            return stale
        if loaded is None:  # too slow to wait for
            return Answer(stored.value, CacheStatus.STALE_IF_SLOW, state.load_seconds, stored.entry.stale_at)
        return loaded

    async def _serve_from_fallback(self, state: CallState, load: AsyncLoad[V]) -> Answer:
        kept = self._codec.decode(state.key, await self._fallback.get(state.key), ())  # the fallback keeps no tags
        if kept is not None:
            if kept.entry.negative:
                return Answer(None, CacheStatus.NOT_FOUND)
            return Answer(kept.value, CacheStatus.FALLBACK, stale_at=kept.entry.stale_at)
        try:
            value = await self._run(state, load)
        except Exception as error:
            if not self._policy.is_negative(error):
                raise
            await self._fallback.set(state.key, self._codec.encode_negative(state))
            raise NotFoundError(state.key) from error
        await self._fallback.set(state.key, self._codec.encode_loaded(state, value))
        return Answer(value, CacheStatus.MISS, state.load_seconds)
