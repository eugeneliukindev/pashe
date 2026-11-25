"""msgspec, which rebuilds the type it is given, as JSON or MessagePack: the msgspec extra."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, final, override

from pashe.codecs import Codec
from pashe.errors import CodecError, InvalidOptionsError, MissingExtraError

try:
    import msgspec
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "msgspec", name=error.name) from error

if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["MsgspecJsonCodec", "MsgspecMsgpackCodec"]


class _MsgspecCodec(Codec):
    """What both formats of msgspec share: which msgspec errors are CodecErrors.

    msgspec rebuilds dataclasses, TypedDict, msgspec.Struct, datetimes, UUIDs, enums and more.
    """

    __slots__ = ("_decode", "_encode", "_name")

    def __init__(self, name: str, encode: Callable[[object], bytes], decode: Callable[..., Any]) -> None:
        self._name = name
        self._encode = encode
        self._decode = decode

    @override
    def encode(self, value: object, /) -> bytes:
        try:
            return self._encode(value)
        except (TypeError, msgspec.EncodeError) as error:
            msg = f"cannot encode {type(value).__name__} as {self._name}"
            raise CodecError(msg) from error

    @override
    def check(self, type_: object, /) -> None:
        # msgspec rebuilds a class it does not know only through a dec_hook, which these codecs do not take
        if isinstance(msgspec.inspect.type_info(type_), msgspec.inspect.CustomType):
            msg = f"{type(self).__name__} cannot rebuild {type_!r}: return a dataclass, a msgspec.Struct or a type msgspec knows"
            raise InvalidOptionsError(msg)

    @override
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        try:
            decoded: T = self._decode(data, type=type_)
        except (
            msgspec.DecodeError,
            UnicodeDecodeError,
        ) as error:  # ValidationError is a DecodeError; a str of bad UTF-8 is not
            msg = f"cannot decode {self._name} as {type_!r}"
            raise CodecError(msg) from error
        return decoded


@final
class MsgspecJsonCodec(_MsgspecCodec):
    """msgspec as JSON: rebuilds dataclasses, TypedDict, msgspec.Struct, datetimes, UUIDs, enums and more.

    It writes NaN and infinity as null, as JSON has neither: MsgspecMsgpackCodec keeps them.

    Examples:
        >>> from dataclasses import dataclass
        >>> from pashe.contrib.msgspec import MsgspecJsonCodec
        >>> @dataclass
        ... class User:
        ...     id: int
        >>> codec = MsgspecJsonCodec()
        >>> codec.decode(codec.encode(User(1)), User)
        User(id=1)
    """

    __slots__ = ()

    def __init__(self) -> None:
        """Create the codec."""
        super().__init__("JSON", msgspec.json.encode, msgspec.json.decode)


@final
class MsgspecMsgpackCodec(_MsgspecCodec):
    """msgspec as MessagePack, smaller and faster than JSON: rebuilds dataclasses, TypedDict, msgspec.Struct, datetimes, UUIDs, enums and more.

    Examples:
        >>> from dataclasses import dataclass
        >>> from pashe.contrib.msgspec import MsgspecMsgpackCodec
        >>> @dataclass
        ... class User:
        ...     id: int
        >>> codec = MsgspecMsgpackCodec()
        >>> codec.decode(codec.encode(User(1)), User)
        User(id=1)
    """

    __slots__ = ()

    def __init__(self) -> None:
        """Create the codec."""
        super().__init__("MessagePack", msgspec.msgpack.encode, msgspec.msgpack.decode)
