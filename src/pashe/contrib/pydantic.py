"""JSON through pydantic, for values that are pydantic models: the pydantic extra."""

from __future__ import annotations

from typing import Any, final, override

from pashe.codecs import Codec
from pashe.errors import CodecError, InvalidOptionsError, MissingExtraError

try:
    import pydantic
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "pydantic", name=error.name) from error

import pydantic_core  # a dependency of pydantic

__all__ = ["PydanticCodec"]


@final
class PydanticCodec(Codec):
    """JSON through pydantic: models, and every type a pydantic.TypeAdapter accepts.

    Examples:
        >>> import pydantic
        >>> from pashe.contrib.pydantic import PydanticCodec
        >>> class User(pydantic.BaseModel):
        ...     id: int
        >>> codec = PydanticCodec()
        >>> codec.decode(codec.encode(User(id=1)), User)
        User(id=1)
    """

    __slots__ = ("_adapters",)

    def __init__(self) -> None:
        """Create the codec; check builds one TypeAdapter per type and keeps it."""
        self._adapters: dict[object, pydantic.TypeAdapter[Any]] = {}

    @override
    def check(self, type_: object, /) -> None:
        """Build the TypeAdapter of type_, or refuse a type pydantic has no schema for.

        Args:
            type_: the return type of the cached function, or of an item of a batch.

        Raises:
            InvalidOptionsError: pydantic cannot validate type_, such as a plain class.
        """
        if type_ in self._adapters:
            return
        try:
            self._adapters[type_] = pydantic.TypeAdapter(type_)  # type: ignore[arg-type]  # any type: a schema error refuses it
        except pydantic.PydanticSchemaGenerationError as error:
            msg = f"PydanticCodec cannot rebuild {type_!r}: return a model, a dataclass or a type pydantic validates"
            raise InvalidOptionsError(msg) from error

    @override
    def encode(self, value: object, /) -> bytes:
        try:
            return pydantic_core.to_json(value)
        except pydantic_core.PydanticSerializationError as error:
            msg = f"cannot encode {type(value).__name__} as JSON"
            raise CodecError(msg) from error

    @override
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        self.check(type_)  # a TypeAdapter takes a while to build: one per type, kept
        try:
            decoded: T = self._adapters[type_].validate_json(data)
        except pydantic.ValidationError as error:
            msg = f"cannot decode JSON as {type_!r}"
            raise CodecError(msg) from error
        return decoded
