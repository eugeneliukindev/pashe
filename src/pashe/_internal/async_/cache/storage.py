from __future__ import annotations

import random
from typing import TYPE_CHECKING, Final, final

from pashe._internal.cache.entry import Lookup, pack, unpack
from pashe._internal.cache.keys import KeyPrefix
from pashe.errors import BackendError, CodecError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pashe._internal.async_.backends.backend import AsyncBackend
    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.cache.entry import Generations, Stored
    from pashe._internal.cache.keys import KeyAndTags
    from pashe.hooks import Hook
    from pashe.options import Fallback

type _Read = tuple[bytes | None, Generations]  # an entry as the backend keeps it, and the generations of its tags

_GENERATION_BITS: Final = 62  # leaves room for a counter to count up within 64 bits


@final
class AsyncStorage:
    # Where the entries of a cache live, with the counters of their tags: in the backend, an entry
    # checked against the generations of its tags, or in the fallback, untagged, while the backend
    # fails; a cache without a fallback finds nothing there and keeps nothing. A method named as one of the backend does as that one does and raises; lookup and keep,
    # on the way of a call, tell the hooks of what fails and take the fallback in its place.
    __slots__ = ("_backend", "_fallback", "_hooks", "_invalidations")

    def __init__(
        self,
        backend: AsyncPrefixedBackend,
        *,
        fallback: Fallback[AsyncBackend] | None,
        hooks: Hook,
    ) -> None:
        """``fallback``: under the prefix of the cache, as its backend is; the cache closes it."""
        self._backend = backend
        self._fallback = fallback
        self._hooks = hooks

        self._invalidations = 0  # of this process: a call after one shares no load started before it

    @property
    def invalidations(self) -> int:
        return self._invalidations

    # On the way of a call

    async def lookup(self, key: str, tags: tuple[str, ...]) -> Lookup:
        try:
            raw, tag_generations = await self._read(key, tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET, key, error))
            return self._lookup(key, await self._fallback_get(key), (), from_fallback=True)
        return self._lookup(key, raw, tag_generations)

    async def lookup_many(self, keys_and_tags: Sequence[KeyAndTags]) -> list[Lookup]:
        """The entries of a batch and the generations of their tags, in one call to the backend."""
        counters = list(dict.fromkeys(counter for _, tags in keys_and_tags for counter in _counters(tags)))
        try:
            raws = await self._backend.get_many([*(key for key, _ in keys_and_tags), *counters])
            by_counter = dict(
                zip(counters, await self._tag_generations(counters, raws[len(keys_and_tags) :]), strict=True)
            )
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET_MANY, "", error))
            return [
                self._lookup(key, await self._fallback_get(key), (), from_fallback=True)  # noqa: WPS476 - memory, nothing to win at once
                for key, _ in keys_and_tags
            ]
        return [
            self._lookup(key, raw, tuple(by_counter[counter] for counter in _counters(tags)))
            for (key, tags), raw in zip(keys_and_tags, raws, strict=False)  # raws: the entries, then the counters
        ]

    async def keep(self, lookup: Lookup, stored: Stored | None) -> bool:
        """Whether stored is kept, in the backend or in the fallback.

        None, what the policy does not store, keeps nothing.
        """
        if stored is None:
            return False
        if lookup.from_fallback:
            return await self._keep_in_fallback(lookup.key, stored)
        try:
            await self._backend.set(lookup.key, _packed(stored, lookup.tag_generations), ttl=stored.storage_seconds)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.SET, lookup.key, error))
            return await self._keep_in_fallback(lookup.key, stored)
        return True

    async def keep_many(self, loaded: Sequence[tuple[Lookup, Stored]]) -> None:
        in_fallback = {lookup.key: stored for lookup, stored in loaded if lookup.from_fallback}
        in_backend = {lookup.key: stored for lookup, stored in loaded if not lookup.from_fallback}
        if in_backend:
            tag_generations = {lookup.key: lookup.tag_generations for lookup, _ in loaded}
            raws = {key: _packed(stored, tag_generations[key]) for key, stored in in_backend.items()}
            try:
                await self._backend.set_many(raws, ttl=max(stored.storage_seconds for stored in in_backend.values()))
            except BackendError as error:
                self._hooks.on_error(Failure(Operation.SET_MANY, "", error))
                in_fallback.update(in_backend)
        for key, stored in in_fallback.items():
            await self._keep_in_fallback(key, stored)  # noqa: WPS476 - memory, nothing to win at once

    async def replace(self, lookup: Lookup, stored: Stored | None) -> None:
        """Keep what refresh loaded in place of what lookup found.

        None, what the policy does not store, deletes it, as the old result must not answer
        after a refresh. A failing backend raises, unless the lookup already went to the
        fallback, which keeps nothing to delete.
        """
        if stored is not None:
            await self.keep(lookup, stored)
        elif not lookup.from_fallback:
            await self._backend.delete(lookup.key)

    # By hand, as the backend does: a failing backend raises

    async def get(self, key: str, tags: tuple[str, ...]) -> Lookup:
        raw, tag_generations = await self._read(key, tags)
        return self._lookup(key, raw, tag_generations)

    async def set(
        self,
        key: str,
        tags: tuple[str, ...],
        stored: Stored | None,
    ) -> None:
        """None, what the policy does not store, deletes what is stored."""
        if stored is None:
            await self._backend.delete(key)
            return
        tag_generations: Generations = ()
        if tags:
            counters = _counters(tags)
            tag_generations = await self._tag_generations(counters, await self._backend.get_many(counters))
        await self._backend.set(key, _packed(stored, tag_generations), ttl=stored.storage_seconds)

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)

    async def invalidate_tags(self, tags: Sequence[str]) -> None:
        # an invalidation is rare: one write after another is fine
        try:
            for counter in _counters(tags):
                await self._backend.set_if_absent(counter, _random_start())  # noqa: WPS476 - INCRBY alone would start at 1
                await self._backend.incr(counter, 1)  # noqa: WPS476 - as above
        finally:  # counted after the writes: a load that started meanwhile may have read the old data
            self._invalidations += 1

    def _lookup(
        self,
        key: str,
        raw: bytes | None,
        tag_generations: Generations,
        *,
        from_fallback: bool = False,
    ) -> Lookup:
        """An entry cut short, of another format, or of a tag invalidated after it was stored, is no entry."""
        if raw is None:
            return Lookup(key, None, tag_generations, from_fallback)
        try:
            entry = unpack(raw)
        except CodecError as error:
            self._hooks.on_error(Failure(Operation.DECODE, key, error))
            return Lookup(key, None, tag_generations, from_fallback)
        return Lookup(key, entry if entry.tag_generations == tag_generations else None, tag_generations, from_fallback)

    async def _fallback_get(self, key: str) -> bytes | None:
        """None with no fallback, or one that fails too."""
        if self._fallback is None:
            return None
        try:
            return await self._fallback.backend.get(key)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.FALLBACK_GET, key, error))
            return None

    async def _keep_in_fallback(self, key: str, stored: Stored) -> bool:
        """Keep stored in the fallback, untagged, as no invalidation reaches it while the backend is down.

        Kept while fresh, or for the ttl of the fallback if that is shorter.
        """
        if self._fallback is None:
            return False
        fresh_seconds, ttl = stored.fresh_seconds, self._fallback.ttl
        try:
            await self._fallback.backend.set(
                key, _packed(stored, ()), ttl=min(fresh_seconds, ttl) if fresh_seconds > 0 else ttl
            )
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.FALLBACK_SET, key, error))
            return False
        return True

    async def _read(self, key: str, tags: Sequence[str]) -> _Read:
        if not tags:
            return await self._backend.get(key), ()
        counters = _counters(tags)
        raws = await self._backend.get_many([key, *counters])
        return raws[0], await self._tag_generations(counters, raws[1:])

    async def _tag_generations(self, counters: Sequence[str], raws: Sequence[bytes | None]) -> Generations:
        parsed = [_parse(raw) for raw in raws if raw is not None]
        if len(parsed) == len(raws):  # every counter exists, as on almost every call: no task per tag
            return tuple(parsed)
        pairs = zip(counters, raws, strict=True)
        return tuple([await self._counter_or_create(counter, raw) for counter, raw in pairs])  # noqa: WPS476 - once per new tag

    async def _counter_or_create(self, counter: str, raw: bytes | None) -> int:
        if raw is not None:
            return _parse(raw)
        start = _random_start()
        if await self._backend.set_if_absent(counter, start):
            return _parse(start)
        created = await self._backend.get(counter)  # another caller created it first
        return _parse(created or start)


def _counters(tags: Sequence[str]) -> list[str]:
    return [KeyPrefix.TAG + tag for tag in tags]


def _random_start() -> bytes:
    return str(random.getrandbits(_GENERATION_BITS)).encode()


def _parse(raw: bytes) -> int:
    try:
        return int(raw)
    except ValueError as error:
        msg = "a tag counter is not an integer"
        raise CodecError(msg) from error


def _packed(stored: Stored, tag_generations: Generations) -> bytes:
    return pack(stored.entry._replace(tag_generations=tag_generations))
