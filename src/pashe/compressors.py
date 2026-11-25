"""What shrinks the bytes of a codec before they are stored; ZstdCompressor is in pashe.contrib.zstd."""

from __future__ import annotations

import zlib
from abc import ABC, abstractmethod
from typing import Final, final, override

from pashe._internal.checks import parse_int
from pashe.errors import CodecError

__all__ = ["Compressor", "GzipCompressor", "NoOpCompressor"]


_GZIP: Final = 31  # the wbits of zlib for the gzip format, as gzip.compress with mtime=0 makes it
_FASTEST: Final = 1
_MIN_SIZE: Final = 1024  # a shorter value shrinks little for the time it costs
_SMALLEST: Final = 9


class Compressor(ABC):
    """Shrinks the bytes a codec produced and restores them; it knows nothing of values.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.compressors import GzipCompressor
        >>> cache = Cache(MemoryBackend(), compressor=GzipCompressor())
    """

    __slots__ = ()

    @property
    def min_size(self) -> int:
        """Bytes of the codec from which a value is compressed; a shorter one is stored as it is.

        A value is kept compressed only if that made it smaller. 0 by default: every value.

        Examples:
            >>> from pashe.compressors import GzipCompressor
            >>> GzipCompressor().min_size
            1024
        """
        return 0

    @abstractmethod
    def compress(self, data: bytes, /) -> bytes:
        """Return data shrunk.

        Args:
            data: the bytes of the codec.

        Returns:
            The shrunk bytes.

        Examples:
            >>> from pashe.compressors import GzipCompressor
            >>> len(GzipCompressor().compress(b"pashe" * 1000)) < 5000
            True
        """
        raise NotImplementedError

    @abstractmethod
    def decompress(self, data: bytes, /) -> bytes:
        """Return the bytes compress was given.

        Args:
            data: the bytes compress made.

        Returns:
            The bytes of the codec.

        Raises:
            CodecError: data was not made by compress.

        Examples:
            >>> from pashe.compressors import GzipCompressor
            >>> compressor = GzipCompressor()
            >>> compressor.decompress(compressor.compress(b"pashe"))
            b'pashe'
        """
        raise NotImplementedError


@final
class GzipCompressor(Compressor):
    """gzip at a level from 1, the fastest, to 9, the smallest.

    Examples:
        >>> from pashe.compressors import GzipCompressor
        >>> compressor = GzipCompressor(level=9)
    """

    __slots__ = ("_level", "_min_size")

    def __init__(self, *, level: int = 6, min_size: int = _MIN_SIZE) -> None:
        """Create the compressor.

        Args:
            level: from 1, the fastest, to 9, the smallest.
            min_size: bytes of the codec from which a value is compressed: a short value shrinks
                little and costs the time to compress it; 0 compresses every value.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: level is not from 1 to 9, or min_size is negative.
        """
        self._level = parse_int(
            "GzipCompressor.level",
            level,
            low=_FASTEST,
            high=_SMALLEST,
            meaning="from 1, the fastest, to 9, the smallest",
        )
        self._min_size = parse_int(
            "GzipCompressor.min_size",
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
        return zlib.compress(data, self._level, wbits=_GZIP)

    @override
    def decompress(self, data: bytes, /) -> bytes:
        try:
            return zlib.decompress(data, wbits=_GZIP)
        except zlib.error as error:
            msg = "not gzip data"
            raise CodecError(msg) from error


@final
class NoOpCompressor(Compressor):
    """Stores the bytes of the codec as they are: what a cache has unless it is given a compressor.

    Examples:
        >>> from pashe.compressors import NoOpCompressor
        >>> NoOpCompressor().compress(b"pashe")
        b'pashe'
    """

    __slots__ = ()

    @override
    def compress(self, data: bytes, /) -> bytes:
        return data

    @override
    def decompress(self, data: bytes, /) -> bytes:
        return data  # a payload another cache compressed then fails in the codec: a miss
