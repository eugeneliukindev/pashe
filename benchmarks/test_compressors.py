from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmarks.products import COUNTS, products
from pashe.compressors import Compressor, GzipCompressor, NoOpCompressor
from pashe.contrib.msgspec import MsgspecMsgpackCodec
from pashe.contrib.zstd import ZstdCompressor

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

    from benchmarks.conftest import RecordBytes

_COMPRESSORS: dict[str, Compressor] = {
    "none": NoOpCompressor(),
    "ZstdCompressor(level=3)": ZstdCompressor(level=3),
    "GzipCompressor(level=6)": GzipCompressor(level=6),
    "GzipCompressor(level=1)": GzipCompressor(level=1),
}


def _data(count: int) -> bytes:
    """What a compressor gets: the bytes of a codec."""
    return MsgspecMsgpackCodec().encode(products(count))


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("name", _COMPRESSORS)
def test_compress(
    name: str,
    count: int,
    benchmark: BenchmarkFixture,
    record_bytes: RecordBytes,
) -> None:
    compressor = _COMPRESSORS[name]
    data = _data(count)
    benchmark.group = f"compressors: compress {count} products as MessagePack"

    compressed = benchmark(compressor.compress, data)

    record_bytes(len(compressed), given=len(data))
    assert compressor.decompress(compressed) == data


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("name", _COMPRESSORS)
def test_decompress(name: str, count: int, benchmark: BenchmarkFixture) -> None:
    compressor = _COMPRESSORS[name]
    data = _data(count)
    compressed = compressor.compress(data)
    benchmark.group = f"compressors: decompress {count} products as MessagePack"

    decompressed = benchmark(compressor.decompress, compressed)

    assert decompressed == data


def test_one_product_grows_when_compressed() -> None:
    one = _data(1)

    sizes = [len(one), len(ZstdCompressor(level=3).compress(one)), len(GzipCompressor(level=6).compress(one))]

    assert sizes == [87, 96, 105]  # the header of the format outweighs what it saves, as the page says
