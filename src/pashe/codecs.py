"""Formats that turn values into bytes and back.

JsonCodec, the default, and PickleCodec need nothing. The others live in pashe.contrib, a
module per extra; importing one without its extra raises MissingExtraError with the command
that installs it::

    from pashe.contrib.msgspec import MsgspecJsonCodec  # pip install "pashe[msgspec]"
"""

from __future__ import annotations

import hashlib
import hmac
import json
import pickle
from abc import ABC, abstractmethod
from typing import Final, final, override

from pashe._internal.checks import expect_json_type, parse_secret
from pashe.errors import CodecError

__all__ = ["Codec", "JsonCodec", "PickleCodec"]


_JSON_ENCODER: Final = json.JSONEncoder(separators=(",", ":"), ensure_ascii=False, allow_nan=False)
_JSON_DECODER: Final = json.JSONDecoder()  # json.loads of bytes would guess their encoding: pashe writes UTF-8
_SIGNATURE_SIZE: Final = hashlib.sha256().digest_size
_UNPICKLE_ERRORS: Final = (pickle.UnpicklingError, AttributeError, ImportError, EOFError, TypeError, ValueError)


class Codec(ABC):
    """Turns a value into bytes and back: the format of what is stored.

    Examples:
        A codec of your own implements encode and decode:

        >>> import json
        >>> from pashe.codecs import Codec
        >>> class Utf8Json(Codec):
        ...     def encode(self, value, /):
        ...         return json.dumps(value).encode()
        ...
        ...     def decode(self, data, type_, /):
        ...         return json.loads(data)
    """

    __slots__ = ()

    @abstractmethod
    def encode(self, value: object, /) -> bytes:
        """Return value as bytes.

        Args:
            value: the value to store.

        Returns:
            The bytes that decode reads back.

        Raises:
            CodecError: value has a type the format cannot hold.

        Examples:
            >>> from pashe.codecs import JsonCodec
            >>> JsonCodec().encode({"id": 1})
            b'{"id":1}'
        """
        raise NotImplementedError

    @abstractmethod
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        """Return data as a value of type_, the return type of the cached function.

        The bytes do not name the type of what was stored, so type_ says what to rebuild, such
        as a dataclass from a JSON object. A codec that cannot rebuild types returns what its
        parser gives: dict, list, str, numbers, bool and None.

        Args:
            data: the bytes encode made.
            type_: the type to rebuild; ``typing.Any`` for what the parser gives.

        Returns:
            The value.

        Raises:
            CodecError: data is not of this format, or does not fit type_.

        Examples:
            >>> from pashe.codecs import JsonCodec
            >>> JsonCodec().decode(b'{"id":1}', dict)
            {'id': 1}
        """
        raise NotImplementedError

    def check(self, type_: object, /) -> None:  # noqa: B027 - optional: a codec that rebuilds any type leaves it
        """Refuse a type the codec cannot give back as it is; it takes every type by default.

        The cache calls it once with the return type, when it decorates the function: a type the
        codec would read back as another one, such as a dataclass as a dict, fails at once instead
        of every result being lost. A type it takes must come back from decode as encode got it:
        the cache then answers a miss with the result itself, as the hits after it read it.

        Args:
            type_: the return type of the cached function, or of an item of a batch.

        Raises:
            InvalidOptionsError: the codec reads values of type_ back as another type.

        Examples:
            >>> from dataclasses import dataclass
            >>> from pashe.codecs import JsonCodec
            >>> @dataclass
            ... class User:
            ...     id: int
            >>> JsonCodec().check(dict[str, int])
            >>> JsonCodec().check(User)
            Traceback (most recent call last):
            ...
            pashe.errors.InvalidOptionsError: JsonCodec reads User back as another type: ...
        """


@final
class JsonCodec(Codec):
    """JSON through the json module, for values JSON holds as they are: dict, list, str, numbers, bool, None.

    It reads back what it wrote as those types, so a TypedDict works. A function that returns
    another type at any depth, such as a dataclass, a model, the tuples of list[tuple[int, int]]
    or the int keys of dict[int, str], is refused with InvalidOptionsError when it is decorated:
    for those use MsgspecJsonCodec or PydanticCodec. It is the default codec.

    Examples:
        >>> from pashe.codecs import JsonCodec
        >>> codec = JsonCodec()
        >>> codec.decode(codec.encode({"id": 1, "tags": ["a"]}), dict)
        {'id': 1, 'tags': ['a']}
    """

    __slots__ = ()

    @override
    def encode(self, value: object, /) -> bytes:
        try:
            return _JSON_ENCODER.encode(value).encode()
        except (TypeError, ValueError) as error:
            msg = f"cannot encode {type(value).__name__} as JSON"
            raise CodecError(msg) from error

    @override
    def check(self, type_: object, /) -> None:
        expect_json_type("JsonCodec", type_)

    @override
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        try:
            decoded: T = _JSON_DECODER.decode(data.decode())
        except ValueError as error:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
            msg = "not JSON"
            raise CodecError(msg) from error
        return decoded


@final
class PickleCodec(Codec):
    """pickle: any object pickle can hold, rebuilt from the class it names; type_ is not used.

    Unpickling runs code chosen by the bytes, so whoever can write to the backend could run code
    wherever it is read. Every value is therefore signed with HMAC-SHA256 under
    secret, and a value whose signature does not match is a CodecError, never unpickled. Keep
    the secret out of the backend and the same for every cache that reads it.

    Entries name their classes: after a class is renamed or moved, old entries are misses.
    They are readable by Python only, not by other services.
    """

    __slots__ = ("_secret",)

    def __init__(self, *, secret: str | bytes) -> None:
        """Create the codec.

        Args:
            secret: the key of the signatures, the same for every cache that reads the backend
                and kept out of it; at least 16 bytes.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: secret is shorter than 16 bytes.

        Examples:
            >>> from pashe.codecs import PickleCodec
            >>> codec = PickleCodec(secret="a secret of sixteen bytes or more")
            >>> codec.decode(codec.encode({1, 2}), set)
            {1, 2}
        """
        self._secret = parse_secret("PickleCodec.secret", secret)

    @override
    def encode(self, value: object, /) -> bytes:
        try:
            data = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PicklingError, TypeError, AttributeError) as error:
            msg = f"cannot pickle {type(value).__name__}"
            raise CodecError(msg) from error
        return self._sign(data) + data

    @override
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        signature, payload = data[:_SIGNATURE_SIZE], data[_SIGNATURE_SIZE:]
        if not hmac.compare_digest(signature, self._sign(payload)):
            msg = "the signature of a pickled value does not match the secret"
            raise CodecError(msg)
        try:
            decoded: T = pickle.loads(payload)  # noqa: S301 - signed by our secret, checked above
        except _UNPICKLE_ERRORS as error:
            msg = "cannot unpickle the value"
            raise CodecError(msg) from error
        return decoded

    def _sign(self, data: bytes) -> bytes:
        return hmac.digest(self._secret, data, hashlib.sha256)
