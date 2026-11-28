from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any

import pytest

from benchmarks.products import COUNTS, Product, product_dicts, products
from pashe.codecs import Codec, JsonCodec, PickleCodec
from pashe.contrib.msgspec import MsgspecJsonCodec, MsgspecMsgpackCodec
from pashe.contrib.pydantic import PydanticCodec

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

    from benchmarks.conftest import RecordBytes

# a codec, whether it rebuilds the products or gives back dicts, as each codec does on a page
_CODECS: dict[str, tuple[Codec, bool]] = {
    "JsonCodec": (JsonCodec(), False),
    "MsgspecJsonCodec": (MsgspecJsonCodec(), True),
    "MsgspecMsgpackCodec": (MsgspecMsgpackCodec(), True),
    "PydanticCodec": (PydanticCodec(), True),
    "PickleCodec": (PickleCodec(secret="a secret of sixteen bytes or more"), True),
}
if importlib.util.find_spec("orjson") is not None:  # orjson has no build for a Python without the GIL
    from pashe.contrib.orjson import OrjsonCodec

    _CODECS["OrjsonCodec"] = (OrjsonCodec(), False)


def _value(name: str, count: int) -> tuple[object, Any]:
    """What the codec stores, and the type it decodes it as. Any: a type form such as list[Product] is no type[T]."""
    if _CODECS[name][1]:
        return products(count), list[Product]
    return product_dicts(count), list[dict[str, object]]


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("name", _CODECS)
def test_encode(
    name: str,
    count: int,
    benchmark: BenchmarkFixture,
    record_bytes: RecordBytes,
) -> None:
    codec, _ = _CODECS[name]
    value, form = _value(name, count)
    benchmark.group = f"codecs: encode {count} products"

    data = benchmark(codec.encode, value)

    record_bytes(len(data))
    assert codec.decode(data, form) == value


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("name", _CODECS)
def test_decode(name: str, count: int, benchmark: BenchmarkFixture) -> None:
    codec, _ = _CODECS[name]
    value, form = _value(name, count)
    data = codec.encode(value)
    benchmark.group = f"codecs: decode {count} products"

    decoded = benchmark(codec.decode, data, form)

    assert decoded == value
