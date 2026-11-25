"""JSON through orjson: faster than the json module, for the same types: the orjson extra."""

from __future__ import annotations

from typing import final, override

from pashe._internal.checks import expect_json_type
from pashe.codecs import Codec
from pashe.errors import CodecError, MissingExtraError

try:
    import orjson
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "orjson", name=error.name) from error


__all__ = ["OrjsonCodec"]


@final
class OrjsonCodec(Codec):
    """JSON through orjson: faster than JsonCodec, and reads back the same types.

        orjson also writes dataclasses and datetimes, but reads them back as dict and str. It writes
        NaN and infinity as null, which reads back as None, where JsonCodec refuses to store them.

    Examples:
        >>> from pashe.contrib.orjson import OrjsonCodec
        >>> codec = OrjsonCodec()
        >>> codec.decode(codec.encode({"id": 1}), dict)
        {'id': 1}
    """

    __slots__ = ()

    @override
    def encode(self, value: object, /) -> bytes:
        try:
            return orjson.dumps(value)
        except TypeError as error:  # orjson.JSONEncodeError is a TypeError
            msg = f"cannot encode {type(value).__name__} as JSON"
            raise CodecError(msg) from error

    @override
    def check(self, type_: object, /) -> None:
        expect_json_type("OrjsonCodec", type_)  # it writes a dataclass, and reads it back as a dict

    @override
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        try:
            decoded: T = orjson.loads(data)
        except orjson.JSONDecodeError as error:
            msg = "not JSON"
            raise CodecError(msg) from error
        return decoded
