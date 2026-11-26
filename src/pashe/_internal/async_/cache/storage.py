from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, final

from pashe._internal.cache.entry import Lookup, pack, unpack
from pashe.errors import BackendError, CodecError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend
    from pashe._internal.async_.cache.fallback import AsyncFallbackStore
    from pashe._internal.async_.cache.tags import AsyncTags
    from pashe._internal.cache.entry import Generations, Stored
    from pashe._internal.cache.keys import KeyAndTags
    from pashe.hooks import Hook


@final
class AsyncStorage:
    # Where the entries of a cache live: in the backend, checked against the generations of their
    # tags, or in the fallback, untagged, while the backend fails. On the way of a call a failing
    # backend goes to the hooks and the fallback takes its place; what is done by hand raises.
    __slots__ = ("_backend", "_fallback", "_hooks", "_tags")

    def __init__(
        self,
        backend: AsyncPrefixedBackend,
        *,
        tags: AsyncTags,
        fallback: AsyncFallbackStore,
        hooks: Hook,
    ) -> None:
        self._backend = backend
        self._tags = tags
        self._fallback = fallback
        self._hooks = hooks

    # For a call

    async def find(self, key: str, tags: tuple[str, ...]) -> Lookup:
        try:
            return await self.get(key, tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET, key, error))
        return await self._read_fallback(key)

    async def find_many(self, keys_and_tags: Sequence[KeyAndTags]) -> list[Lookup]:
        # the entries of a batch and the generations of their tags, in one call to the backend
        try:
            found = await self._tags.read_many(keys_and_tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.GET_MANY, "", error))
            return [await self._read_fallback(key) for key, _ in keys_and_tags]  # noqa: WPS476 - memory, nothing to win at once
        return [
            self._lookup(key, raw, generations)
            for (key, _), (raw, generations) in zip(keys_and_tags, found, strict=True)
        ]

    async def open(self, key: str, tags: tuple[str, ...]) -> Lookup:
        # the generations alone, for a load that reads no entry
        try:
            generations = await self._tags.generations(tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.READ_TAGS, key, error))
            return Lookup(key, None, from_fallback=True)
        return Lookup(key, None, generations)

    async def open_many(self, keys_and_tags: Sequence[KeyAndTags]) -> list[Lookup]:
        # the generations alone, for the items of a batch that read no entry
        try:
            found = await self._tags.read_many(keys_and_tags)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.READ_TAGS, "", error))
            return [Lookup(key, None, from_fallback=True) for key, _ in keys_and_tags]
        return [Lookup(key, None, generations) for (key, _), (_, generations) in zip(keys_and_tags, found, strict=True)]

    async def keep(self, lookup: Lookup, stored: Stored | None) -> None:
        # None, what the policy does not store, keeps nothing
        if stored is None:
            return
        if lookup.from_fallback:
            await self._keep_in_fallback(lookup.key, stored)
            return
        try:
            await self._backend.set(lookup.key, _packed(stored, lookup.generations), ttl=stored.storage_seconds)
        except BackendError as error:
            self._hooks.on_error(Failure(Operation.SET, lookup.key, error))
            await self._keep_in_fallback(lookup.key, stored)

    async def keep_many(self, loaded: Sequence[tuple[Lookup, Stored]]) -> None:
        in_fallback = {lookup.key: stored for lookup, stored in loaded if lookup.from_fallback}
        in_backend = {lookup.key: stored for lookup, stored in loaded if not lookup.from_fallback}
        if in_backend:
            generations = {lookup.key: lookup.generations for lookup, _ in loaded}
            raws = {key: _packed(stored, generations[key]) for key, stored in in_backend.items()}
            try:
                await self._backend.set_many(raws, ttl=max(stored.storage_seconds for stored in in_backend.values()))
            except BackendError as error:
                self._hooks.on_error(Failure(Operation.SET_MANY, "", error))
                in_fallback.update(in_backend)
        for key, stored in in_fallback.items():
            await self._keep_in_fallback(key, stored)  # noqa: WPS476 - memory, nothing to win at once

    # By hand

    async def get(self, key: str, tags: tuple[str, ...]) -> Lookup:
        raw, generations = await self._tags.read(key, tags)
        return self._lookup(key, raw, generations)

    async def set(
        self,
        key: str,
        tags: tuple[str, ...],
        stored: Stored | None,
    ) -> None:
        # None, what the policy does not store, deletes what is stored
        if stored is None:
            await self._backend.delete(key)
            return
        generations = await self._tags.generations(tags)
        await self._backend.set(key, _packed(stored, generations), ttl=stored.storage_seconds)

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)

    def _lookup(
        self,
        key: str,
        raw: bytes | None,
        generations: Generations,
        *,
        from_fallback: bool = False,
    ) -> Lookup:
        # an entry cut short, of another format, or of a tag invalidated after it was stored, is no entry
        if raw is None:
            return Lookup(key, None, generations, from_fallback)
        try:
            entry = unpack(raw)
        except CodecError as error:
            self._hooks.on_error(Failure(Operation.DECODE, key, error))
            return Lookup(key, None, generations, from_fallback)
        return Lookup(key, entry if entry.tag_generations == generations else None, generations, from_fallback)

    async def _read_fallback(self, key: str) -> Lookup:
        return self._lookup(key, await self._fallback.get(key), (), from_fallback=True)

    async def _keep_in_fallback(self, key: str, stored: Stored) -> None:
        # untagged: no invalidation reaches the fallback while the backend is down
        await self._fallback.set(key, _packed(stored, ()), fresh_seconds=stored.fresh_seconds)


def _packed(stored: Stored, generations: Generations) -> bytes:
    return pack(replace(stored.entry, tag_generations=generations))
