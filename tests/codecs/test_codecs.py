"""Every codec and compressor reads back what it wrote, and says when it cannot."""

from __future__ import annotations

import importlib
import pickle
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

import pytest

from pashe.codecs import JsonCodec, PickleCodec
from pashe.compressors import GzipCompressor
from pashe.contrib.msgspec import MsgspecJsonCodec, MsgspecMsgpackCodec
from pashe.contrib.pydantic import PydanticCodec
from pashe.contrib.zstd import ZstdCompressor
from pashe.errors import CodecError, InvalidOptionsError, MissingExtraError
from tests.harness.helpers import json_codecs

if TYPE_CHECKING:
    from collections.abc import Callable

    from pashe.codecs import Codec
    from pashe.compressors import Compressor


@dataclass
class User:
    id: int
    name: str
    seen: datetime


class UserDict(TypedDict):
    id: int
    name: str


_SECRET = "a secret of 16+ bytes"
_TYPED = [MsgspecJsonCodec(), MsgspecMsgpackCodec(), PydanticCodec(), PickleCodec(secret=_SECRET)]
_DATA = [*json_codecs(), *_TYPED[:3]]  # codecs that store data, not objects
_ALL = [*json_codecs(), *_TYPED]


@pytest.mark.parametrize("codec", _ALL, ids=lambda codec: type(codec).__name__)
@pytest.mark.parametrize(
    ("value", "type_"),
    [
        ({"id": 1, "name": "Ann"}, UserDict),
        ([1, 2.5, "x", True, None], list),
        ("plain", str),
        (42, int),
    ],
)
def test_plain_values_read_back(codec: Codec, value: object, type_: type) -> None:
    assert codec.decode(codec.encode(value), type_) == value


@pytest.mark.parametrize("codec", _TYPED, ids=lambda codec: type(codec).__name__)
def test_typed_codecs_rebuild_the_type(codec: Codec) -> None:
    user = User(1, "Ann", datetime(2026, 11, 22, tzinfo=UTC))
    assert codec.decode(codec.encode(user), User) == user


def test_json_returns_what_the_parser_gives() -> None:
    codec = JsonCodec()
    decoded: object = codec.decode(codec.encode({"id": 1}), User)
    assert decoded == {"id": 1}


@pytest.mark.parametrize("codec", _ALL, ids=lambda codec: type(codec).__name__)
def test_broken_data_is_a_codec_error(codec: Codec) -> None:
    with pytest.raises(CodecError):
        codec.decode(b"\xff{not data", User if codec in _TYPED else dict)


@pytest.mark.parametrize("codec", _DATA, ids=lambda codec: type(codec).__name__)
def test_value_it_cannot_hold_is_a_codec_error(codec: Codec) -> None:
    with pytest.raises(CodecError):
        codec.encode(object())


@pytest.mark.parametrize("codec", [MsgspecJsonCodec(), MsgspecMsgpackCodec()], ids=lambda codec: type(codec).__name__)
def test_a_str_of_broken_utf8_is_a_codec_error(codec: Codec) -> None:
    broken = codec.encode("e")[:-1] + b"\xff"

    with pytest.raises(CodecError):
        codec.decode(broken, str)


@pytest.mark.parametrize("form", [tuple[int, int], set[int], frozenset[str]], ids=repr)
def test_json_refuses_a_generic_it_reads_back_as_a_list(form: object) -> None:
    with pytest.raises(InvalidOptionsError, match="back as another type"):
        JsonCodec().check(form)


type _Pair = tuple[int, int]


def test_json_refuses_what_a_type_alias_stands_for() -> None:
    with pytest.raises(InvalidOptionsError, match="reads tuple back"):
        JsonCodec().check(_Pair)


def test_pickle_rejects_what_it_cannot_pickle() -> None:
    with pytest.raises(CodecError):
        PickleCodec(secret=_SECRET).encode(lambda: None)


def test_pickle_never_unpickles_bytes_it_did_not_sign() -> None:
    signed = PickleCodec(secret=_SECRET).encode({"id": 1})
    middle = len(signed) // 2
    tampered = signed[:middle] + bytes([signed[middle] ^ 1]) + signed[middle + 1 :]
    with pytest.raises(CodecError, match="signature"):
        PickleCodec(secret=_SECRET).decode(tampered, dict)
    with pytest.raises(CodecError, match="signature"):
        PickleCodec(secret="another secret, 16+").decode(signed, dict)


def test_pickle_needs_a_long_secret() -> None:
    with pytest.raises(InvalidOptionsError):
        PickleCodec(secret="short")


@pytest.mark.parametrize("compressor", [GzipCompressor(), ZstdCompressor()], ids=lambda it: type(it).__name__)
def test_compressors_restore_and_reject(compressor: Compressor) -> None:
    data = b"pashe " * 100
    packed = compressor.compress(data)
    assert len(packed) < len(data)
    assert compressor.decompress(packed) == data
    with pytest.raises(CodecError):
        compressor.decompress(b"not compressed")


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: GzipCompressor(level=10), "GzipCompressor.level is 10"),
        (lambda: ZstdCompressor(level=23), "ZstdCompressor.level is 23"),
        (lambda: GzipCompressor(min_size=-1), "GzipCompressor.min_size is -1"),
        (lambda: ZstdCompressor(min_size=-1), "ZstdCompressor.min_size is -1"),
    ],
)
def test_options_out_of_range_are_refused(make: Callable[[], object], message: str) -> None:
    with pytest.raises(InvalidOptionsError, match=message):
        make()


class _Plain:
    """A class neither msgspec nor pydantic knows how to rebuild."""


@pytest.mark.parametrize(
    "codec", [MsgspecJsonCodec(), MsgspecMsgpackCodec(), PydanticCodec()], ids=lambda it: type(it).__name__
)
def test_a_typed_codec_refuses_a_class_it_cannot_rebuild(codec: Codec) -> None:
    with pytest.raises(InvalidOptionsError, match="cannot rebuild"):
        codec.check(_Plain)


@pytest.mark.parametrize(
    ("module", "dependency", "extra"),
    [
        ("pashe.contrib.orjson", "orjson", "orjson"),
        ("pashe.contrib.msgspec", "msgspec", "msgspec"),
        ("pashe.contrib.pydantic", "pydantic", "pydantic"),
        ("pashe.contrib.fastapi", "fastapi", "fastapi"),
        ("pashe.contrib.redis", "redis", "redis"),
    ],
)
def test_missing_extra_says_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    dependency: str,
    extra: str,
) -> None:
    monkeypatch.setitem(sys.modules, dependency, None)  # None makes the import fail
    monkeypatch.delitem(sys.modules, module, raising=False)  # imported only if another test did
    with pytest.raises(MissingExtraError, match=rf'pip install "pashe\[{extra}\]"') as raised:
        importlib.import_module(module)
    assert (raised.value.extra, raised.value.name) == (extra, dependency)
    assert str(pickle.loads(pickle.dumps(raised.value))) == str(raised.value)  # noqa: S301 - our own bytes
