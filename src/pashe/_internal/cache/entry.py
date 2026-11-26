from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, final

from pashe._internal.cache.value_types import fingerprint
from pashe.errors import CodecError, InvalidOptionsError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from pashe._internal.cache.policy import Policy
    from pashe.codecs import Codec
    from pashe.compressors import Compressor
    from pashe.hooks import Hook

_VERSION: Final = b"\x03"  # the format of an entry, its first byte; 3 says whether the payload is compressed
_HEADER: Final = struct.Struct("!dBQH")  # stale_at, flags, type_fingerprint, how many generations of tags follow
_NEGATIVE: Final = 1  # a flag: the entry keeps a "not found"
_COMPRESSED: Final = 2  # a flag: the payload went through the compressor
_HEADER_END: Final = len(_VERSION) + _HEADER.size


type Generations = tuple[int, ...]  # of the tags of a result, in the order of its tags


@final
class EntryFormat:
    # How the results of one cached function become entries and back. Its policy decides which are
    # stored and for how long, the codec and the compressor make the payload, and the fingerprint
    # of the type tells an entry of another type. What fails on the way goes to the hooks, as a
    # miss, not an error.
    __slots__ = ("_codec", "_compressor", "_hooks", "_policy", "_type", "_type_fingerprint")

    def __init__(
        self,
        policy: Policy,
        type_: object,
        *,
        codec: Codec,
        compressor: Compressor,
        hooks: Hook,
    ) -> None:
        codec.check(type_)  # a type the codec gives back as another one is refused here

        self._policy = policy
        self._type: Any = type_
        self._codec = codec
        self._compressor = compressor
        self._hooks = hooks

        self._type_fingerprint = fingerprint(type_)

    def encode_loaded(
        self,
        result: object,
        *,
        load_seconds: float,
        key: str,
    ) -> Stored | None:
        # key names a failure for the hooks
        if not self._policy.should_store_loaded(result, load_seconds):
            return None
        return self._encode(result, key=key)

    def encode(self, result: object, *, key: str) -> Stored | None:
        # a result set by hand: how long a load takes does not count
        if not self._policy.should_store(result):
            return None
        return self._encode(result, key=key)

    def encode_not_found(self) -> Stored | None:
        lifetime = self._policy.negative_lifetime()
        if lifetime is None:
            return None
        entry = Entry(
            self._policy.clock() + lifetime,
            negative=True,
            compressed=False,
            type_fingerprint=self._type_fingerprint,
            tag_generations=(),
            payload=b"",
        )
        return Stored(entry, None, lifetime, storage_seconds=lifetime)  # a "not found" is kept only while fresh

    def decode(self, lookup: Lookup) -> Stored | None:
        # None for no entry, or one stored as another type, such as before a deploy changed it
        entry = lookup.entry
        if entry is None or entry.type_fingerprint != self._type_fingerprint:
            return None
        if entry.negative:
            return Stored(entry, None)
        try:
            data = self._compressor.decompress(entry.payload) if entry.compressed else entry.payload
            return Stored(entry, self._codec.decode(data, self._type))
        except CodecError as error:
            self._hooks.on_error(Failure(Operation.DECODE, lookup.key, error))
            return None

    def _encode(self, result: object, *, key: str) -> Stored | None:
        try:
            lifetime = self._policy.freshness_lifetime(result)
        except InvalidOptionsError as error:  # a ttl of the result that is negative
            self._hooks.on_error(Failure(Operation.TTL, key, error))
            return None
        if lifetime is None:
            return None
        # A miss answers with the result itself: a type check took comes back from the codec as it
        # went in. One left open by Any, or by no annotation, may come back as another type on a hit.
        try:
            data = self._codec.encode(result)
        except CodecError as error:
            self._hooks.on_error(Failure(Operation.ENCODE, key, error))
            return None
        payload = data
        if len(data) >= self._compressor.min_size:
            packed = self._compressor.compress(data)
            if len(packed) < len(data):  # kept only if that makes it smaller
                payload = packed
        entry = Entry(
            self._policy.clock() + lifetime,
            negative=False,
            compressed=payload is not data,
            type_fingerprint=self._type_fingerprint,
            tag_generations=(),
            payload=payload,
        )
        return Stored(entry, result, lifetime, self._policy.storage_seconds(lifetime))


@final
@dataclass(frozen=True, slots=True)
class Stored:
    # an entry with its result; its generations of tags are set where it is stored
    entry: Entry
    result: object  # decoded as the return type
    fresh_seconds: float = 0
    storage_seconds: float = 0  # how long the backend keeps it: fresh, then the stale windows


@final
@dataclass(frozen=True, slots=True)
class Lookup:
    # What a call found under its key: an entry the generations of its tags still match, or none.
    # A load after it stores with these generations, so a tag invalidated meanwhile makes it a miss.
    key: str
    entry: Entry | None
    tag_generations: Generations = ()
    from_fallback: bool = False  # the backend failed: the entry is of the fallback, and a store goes there


@final
@dataclass(frozen=True, slots=True)
class Entry:
    stale_at: float
    negative: bool
    compressed: bool
    type_fingerprint: int
    tag_generations: Generations
    payload: bytes = field(repr=False)  # the bytes of the result, too long to read in a repr


def pack(entry: Entry) -> bytes:
    count = len(entry.tag_generations)
    flags = _NEGATIVE * entry.negative | _COMPRESSED * entry.compressed  # a bool counts as 0 or 1
    header = _HEADER.pack(entry.stale_at, flags, entry.type_fingerprint, count)
    return _VERSION + header + struct.pack(f"!{count}q", *entry.tag_generations) + entry.payload


def unpack(raw: bytes) -> Entry:
    if not raw.startswith(_VERSION):
        msg = "not a cached result of this format"
        raise CodecError(msg)

    stale_at, flags, type_fingerprint, tag_count = _read(_HEADER.format, raw, len(_VERSION))
    layout = f"!{tag_count}q"  # each generation a signed 64-bit integer
    generations = _read(layout, raw, _HEADER_END) if tag_count else ()  # most results have no tags
    payload = raw[_HEADER_END + struct.calcsize(layout) :]
    return Entry(stale_at, bool(flags & _NEGATIVE), bool(flags & _COMPRESSED), type_fingerprint, generations, payload)


def _read(
    layout: str,
    raw: bytes,
    offset: int,
) -> tuple[Any, ...]:
    # struct caches the formats it was given as str, so a layout is compiled once
    try:
        return struct.unpack_from(layout, raw, offset)
    except struct.error as error:
        msg = "not a cached result: it is cut short"
        raise CodecError(msg) from error
