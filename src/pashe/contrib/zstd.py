"""Zstandard: from the standard library on Python 3.14, from backports.zstd before it."""

from __future__ import annotations

import sys
from typing import Final, final, override

from pashe._internal.checks import parse_int
from pashe.compressors import Compressor
from pashe.errors import CodecError, MissingExtraError

if sys.version_info >= (3, 14):
    from compression import zstd
else:
    try:
        from backports import zstd
    except ModuleNotFoundError as error:
        raise MissingExtraError(__name__, "zstd", name=error.name) from error


__all__ = ["ZstdCompressor"]

_FASTEST: Final = 1
_MIN_SIZE: Final = 1024  # a shorter value shrinks little for the time it costs
_SMALLEST: Final = 22


@final
class ZstdCompressor(Compressor):
    """Zstandard at a level from 1, the fastest, to 22, the smallest.

    Examples:
        >>> from pashe.contrib.zstd import ZstdCompressor
        >>> compressor = ZstdCompressor(level=3)
        >>> compressor.decompress(compressor.compress(b"pashe"))
        b'pashe'
    """

    __slots__ = ("_level", "_min_size")

    def __init__(self, *, level: int = 3, min_size: int = _MIN_SIZE) -> None:
        """Create the compressor.

        Args:
            level: from 1, the fastest, to 22, the smallest.
            min_size: bytes of the codec from which a value is compressed: a short value shrinks
                little and costs the time to compress it; 0 compresses every value.

        Raises:
            TypeError: level is not an int.
            InvalidOptionsError: level is not from 1 to 22, or min_size is negative.
        """
        self._level = parse_int(
            "ZstdCompressor.level",
            level,
            low=_FASTEST,
            high=_SMALLEST,
            meaning="from 1, the fastest, to 22, the smallest",
        )
        self._min_size = parse_int(
            "ZstdCompressor.min_size",
            min_size,
            low=0,
            meaning="bytes from which a value is compressed, 0 or more",
        )

    @property
    @override
    def min_size(self) -> int:
        return self._min_size

    @override
    def compress(self, data: bytes, /) -> bytes:
        return zstd.compress(data, level=self._level)  # type: ignore[no-any-return]  # backports.zstd of Python 3.12 has no types

    @override
    def decompress(self, data: bytes, /) -> bytes:
        try:
            restored: bytes = zstd.decompress(data)
        except zstd.ZstdError as error:
            msg = "not Zstandard data"
            raise CodecError(msg) from error
        return restored
