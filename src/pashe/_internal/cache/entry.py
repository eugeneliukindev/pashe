from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, NamedTuple, final

from pashe._internal.cache.value_types import fingerprint
from pashe.errors import CodecError

if TYPE_CHECKING:
    from pashe.codecs import Codec
    from pashe.compressors import Compressor

_VERSION: Final = b"\x03"  # the format of an entry, its first byte; 3 says whether the payload is compressed
_HEADER: Final = struct.Struct("!dBQH")  # stale_at, flags, type_fingerprint, how many generations of tags follow
_NEGATIVE: Final = 1  # a flag: the entry keeps a "not found"
_COMPRESSED: Final = 2  # a flag: the payload went through the compressor
_HEADER_END: Final = len(_VERSION) + _HEADER.size


type Generations = tuple[int, ...]  # of the tags of a result, in the order of its tags


@final
class EntryFormat:
    __slots__ = ("_serializer", "_type", "_type_fingerprint")

    def __init__(self, serializer: Serializer, type_: object) -> None:
        self._serializer = serializer
        self._type: Any = type_

        self._type_fingerprint = fingerprint(type_)

    def encode(
        self,
        value: object,
        *,
        stale_at: float,
        fresh_seconds: float,
        tag_generations: Generations,
    ) -> Stored:
        payload, compressed = self._serializer.encode(value)
        entry = Entry(
            stale_at,
            negative=False,
            compressed=compressed,
            type_fingerprint=self._type_fingerprint,
            tag_generations=tag_generations,
            payload=payload,
        )
        return Stored(entry, self._value_of(entry), fresh_seconds)

    def encode_negative(
        self,
        *,
        stale_at: float,
        fresh_seconds: float,
        tag_generations: Generations,
    ) -> Stored:
        entry = Entry(
            stale_at,
            negative=True,
            compressed=False,
            type_fingerprint=self._type_fingerprint,
            tag_generations=tag_generations,
            payload=b"",
        )
        return Stored(entry, None, fresh_seconds)

    def decode(self, raw: bytes) -> Stored | None:
        # None for an entry stored as another type, such as before a deploy changed it
        entry = unpack(raw)
        if entry.type_fingerprint != self._type_fingerprint:
            return None
        return Stored(entry, None if entry.negative else self._value_of(entry))

    def _value_of(self, entry: Entry) -> object:
        return self._serializer.decode(entry.payload, self._type, compressed=entry.compressed)


@final
@dataclass(frozen=True, slots=True)
class Stored:
    entry: Entry
    value: object  # decoded as the return type
    fresh_seconds: float = 0

    @property
    def raw(self) -> bytes:
        return pack(self.entry)


@final
@dataclass(frozen=True, slots=True)
class Entry:
    stale_at: float
    negative: bool
    compressed: bool
    type_fingerprint: int
    tag_generations: Generations
    payload: bytes


@final
class Serializer:
    # How a value turns into the payload of an entry: through the codec, then through the
    # compressor once it is min_size long and only if that makes it smaller.
    __slots__ = ("_codec", "_compressor")

    def __init__(self, codec: Codec, compressor: Compressor) -> None:
        self._codec = codec
        self._compressor = compressor

    def check(self, type_: object) -> None:
        self._codec.check(type_)

    def encode(self, value: object) -> Payload:
        data = self._codec.encode(value)
        if len(data) < self._compressor.min_size:
            return Payload(data, compressed=False)
        packed = self._compressor.compress(data)
        return Payload(packed, compressed=True) if len(packed) < len(data) else Payload(data, compressed=False)

    def decode[T](
        self,
        data: bytes,
        type_: type[T],
        *,
        compressed: bool,
    ) -> T:
        return self._codec.decode(self._compressor.decompress(data) if compressed else data, type_)


@final
class Payload(NamedTuple):
    # what Serializer made of a value
    data: bytes
    compressed: bool  # whether data went through the compressor


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
