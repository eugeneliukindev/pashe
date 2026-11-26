from __future__ import annotations

import dataclasses
import functools
from typing import TYPE_CHECKING, final

from pashe._internal.async_.cache.reload import AsyncReload
from pashe._internal.async_.locks.locking import atake
from pashe._internal.async_.tasks import AsyncLoadLimit, AsyncSharedLoads
from pashe._internal.cache.call import Answer, Call, in_no_cache
from pashe._internal.cache.keys import KeyPrefix
from pashe.errors import BackendError, NotFoundError
from pashe.hooks import CacheStatus, Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.storage import AsyncStorage
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe._internal.async_.tasks import AsyncBackgroundTasks
    from pashe._internal.cache.call import CallReporter
    from pashe._internal.cache.entry import EntryFormat, Lookup, Stored
    from pashe._internal.cache.policy import Policy
    from pashe.hooks import Hook

type AsyncLoad[V] = Callable[[], Awaitable[V]]  # a call of the cached function with its arguments, run on a miss


@final
class AsyncFunctionCache[V]:
    # The cache of one function: answers from what its storage finds, or loads and keeps. Its
    # policy decides, its format encodes, and it tells the hooks of what it works around.
    __slots__ = (
        "_backend",
        "_changes",
        "_format",
        "_hooks",
        "_load_limit",
        "_policy",
        "_reload",
        "_reporter",
        "_shared_loads",
        "_storage",
        "_tags",
    )

    def __init__(
        self,
        policy: Policy,
        *,
        storage: AsyncStorage,
        entry_format: EntryFormat,
        tags: AsyncTags,
        backend: AsyncPrefixedBackend,
        background: AsyncBackgroundTasks,
        reporter: CallReporter,
        hooks: Hook,
    ) -> None:
        self._policy = policy
        self._storage = storage
        self._format = entry_format
        self._tags = tags  # its invalidations in this process end the sharing of a load
        self._backend = backend  # for the Stampede.lock_for lock
        self._reporter = reporter
        self._hooks = hooks

        # the sets and deletes by hand in this process: a load that started before one stores
        # nothing, and is shared with no call after it
        self._changes = 0
        self._shared_loads = AsyncSharedLoads()
        self._reload = AsyncReload(
            backend=backend, background=background, slow_after=policy.stale.slow_after, hooks=hooks
        )
        self._load_limit = AsyncLoadLimit(policy.stampede.max_loads)

    async def get_or_load(
        self,
        key: str,
        tags: tuple[str, ...],
        load: AsyncLoad[V],
    ) -> V:
        call = Call(key, tags, changes_at_start=self._changes)
        try:
            if in_no_cache():  # it shares no answer: another call may answer from the backend
                answer = await self._load_and_store(call, await self._storage.open(key, tags), load)
            elif self._policy.stampede.share_loads:
                share_key = (
                    key,
                    self._tags.invalidation_count,
                    self._changes,
                )  # no load started before a change is shared
                answer = await self._shared_loads.share(share_key, functools.partial(self._serve, call, load))
            else:
                answer = await self._serve(call, load)
        except Exception:
            self._reporter.report(key, CacheStatus.MISS, load_seconds=call.stopwatch.seconds)
            raise
        return self._result(key, answer)

    async def refresh(
        self,
        key: str,
        tags: tuple[str, ...],
        load: AsyncLoad[V],
    ) -> V:
        call = Call(key, tags, changes_at_start=self._changes)
        lookup = await self._storage.open(key, tags)
        result = await self._run(call, load, has_stale_answer=False)
        stored = self._format.encode_loaded(result, load_seconds=call.stopwatch.seconds, key=key)
        if stored is None and not lookup.from_fallback:
            await self._storage.delete(key)  # the old result must not answer after a refresh
            return result
        await self._keep_unless_changed(call, lookup, stored)
        return result if stored is None or lookup.from_fallback else stored.result  # type: ignore[return-value]  # decoded as the return type

    async def get(self, key: str, tags: tuple[str, ...]) -> V | None:
        # The fresh result alone, loading nothing: a failing backend raises, as there is no load to answer with.
        if in_no_cache():
            self._reporter.report(key, CacheStatus.MISS)
            return None
        answer = self._policy.answer_for(self._format.decode(await self._storage.get(key, tags)))
        if answer is None or answer.status is CacheStatus.STALE_WHILE_REVALIDATE:
            self._reporter.report(key, CacheStatus.MISS)
            return None
        return self._result(key, answer)

    async def set(
        self,
        key: str,
        tags: tuple[str, ...],
        result: V,
    ) -> None:
        self._changes += 1  # before the write: a load that ends after it must not overwrite it
        await self._storage.set(key, tags, self._format.encode(result, key=key))

    async def delete(self, key: str) -> bool:
        self._changes += 1  # before the delete, as in set
        return await self._storage.delete(key)

    def _result(self, key: str, answer: Answer) -> V:
        self._reporter.report(key, answer.status, load_seconds=answer.load_seconds, stale_at=answer.stale_at)
        if answer.status is CacheStatus.NOT_FOUND:
            raise NotFoundError(key)  # kept by an earlier call, as Negative says
        return answer.result  # type: ignore[return-value]  # decoded as the return type

    async def _serve(self, call: Call, load: AsyncLoad[V]) -> Answer:  # noqa: WPS212 - one return for each way a call is answered
        lookup = await self._storage.find(call.key, call.tags)
        stored = self._format.decode(lookup)
        if (
            lookup.from_fallback
        ):  # the backend fails: what the fallback kept answers, untagged, or the load is kept there
            if stored is None:
                return await self._load_and_store(call, lookup, load)
            return (
                Answer(None, CacheStatus.NOT_FOUND)
                if stored.entry.negative
                else Answer.of(stored, CacheStatus.FALLBACK)
            )

        answer = self._policy.answer_for(stored)
        if answer is not None:
            if self._policy.should_revalidate(answer):
                load_and_store = functools.partial(
                    self._load_and_store, lookup=lookup, load=load, has_stale_answer=True
                )
                await self._reload.start(call, load_and_store)  # the old result answered: a full limit skips it
            return answer

        if stored is not None and not stored.entry.negative:
            return await self._serve_stale_or_load(call, lookup, load, stored=stored)
        if self._policy.stampede.lock_for > 0:
            return await self._load_under_lock(call, lookup, load)
        return await self._load_and_store(call, lookup, load)

    async def _run(
        self,
        call: Call,
        load: AsyncLoad[V],
        *,
        has_stale_answer: bool,
    ) -> V:
        # a stale result that can answer skips a full limit of loads
        async with self._load_limit.slot(wait=not has_stale_answer):
            with call.stopwatch.running():
                return await load()

    async def _load_and_store(
        self,
        call: Call,
        lookup: Lookup,
        load: AsyncLoad[V],
        *,
        has_stale_answer: bool = False,
    ) -> Answer:
        try:
            result = await self._run(call, load, has_stale_answer=has_stale_answer)
        except Exception as error:
            if not self._policy.is_negative(error):
                raise
            await self._keep_unless_changed(
                call, lookup, self._format.encode_not_found()
            )  # the answer of the calls after it
            raise NotFoundError(call.key) from error

        stored = self._format.encode_loaded(result, load_seconds=call.stopwatch.seconds, key=call.key)
        await self._keep_unless_changed(call, lookup, stored)
        if stored is None or lookup.from_fallback:
            return Answer(result, CacheStatus.MISS, call.stopwatch.seconds)
        return Answer.of(stored, CacheStatus.MISS, call.stopwatch.seconds)

    async def _keep_unless_changed(
        self,
        call: Call,
        lookup: Lookup,
        stored: Stored | None,
    ) -> None:
        if call.changes_at_start != self._changes:  # set or deleted by hand while it loaded: what it loaded is old
            return
        await self._storage.keep(lookup, stored)

    async def _load_under_lock(  # noqa: WPS231 - the lock, the read after it and the load in one place
        self,
        call: Call,
        lookup: Lookup,
        load: AsyncLoad[V],
    ) -> Answer:
        lock_key = KeyPrefix.STAMPEDE_LOCK + call.key
        try:
            lease = await atake(
                self._backend, (lock_key,), self._policy.stampede.lock_for, name=lock_key, hooks=self._hooks
            )
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.STAMPEDE_LOCK, call.key, error))
            return await self._load_and_store(call, lookup, load)
        try:
            # The load before this one may have stored it. A load after this read stores with its
            # generations; with the backend failing, with those of the read before the lock.
            try:  # noqa: WPS505 - a read that fails loads all the same, and the lock is released either way
                lookup = await self._storage.get(call.key, call.tags)
            except BackendError as error:
                self._hooks.on_error(Failure(Operation.GET, call.key, error))
            else:
                answer = self._policy.answer_for(self._format.decode(lookup))
                if answer is not None:  # a "not found" the load before this one kept answers as it is
                    hit = answer.status is not CacheStatus.NOT_FOUND
                    return dataclasses.replace(answer, status=CacheStatus.HIT) if hit else answer
            return await self._load_and_store(call, lookup, load)
        finally:
            if lease is not None:  # with no timeout it waits until it takes the lock
                await lease.release()

    async def _serve_stale_or_load(
        self,
        call: Call,
        lookup: Lookup,
        load: AsyncLoad[V],
        *,
        stored: Stored,
    ) -> Answer:
        # a result past its TTL that a window of Stale keeps: it answers if the load fails or is slow
        if_error, if_slow = self._policy.stale_windows(stored)
        has_stale_answer = if_error or if_slow
        load_and_store = functools.partial(
            self._load_and_store, lookup=lookup, load=load, has_stale_answer=has_stale_answer
        )
        try:
            loaded = await (
                self._reload.wait_at_most_slow_after(call, load_and_store) if if_slow else load_and_store(call)
            )
        except Exception as error:
            stale_answer = self._policy.stale_answer(
                stored, error, load_seconds=call.stopwatch.seconds, has_stale_answer=has_stale_answer
            )
            if stale_answer is None:
                raise
            self._hooks.on_error(Failure(Operation.LOAD, call.key, error))
            return stale_answer
        if loaded is None:  # too slow to wait for
            return Answer.of(stored, CacheStatus.STALE_IF_SLOW, call.stopwatch.seconds)
        return loaded
