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
        """Create the codec; it builds one TypeAdapter per type, when it first meets the type, and keeps it."""
        self._adapters: dict[object, pydantic.TypeAdapter[Any]] = {}

    @override
    def validate(self, type_: object, /) -> None:
        """Refuse a type pydantic has no schema for.

        Args:
            type_: the return type of the cached function, or of an item of a batch.

        Raises:
            InvalidOptionsError: pydantic cannot validate type_, such as a plain class.
        """
        self._adapter(type_)

    @override
    def encode(self, value: object, /) -> bytes:
        try:
            return pydantic_core.to_json(value)
        except pydantic_core.PydanticSerializationError as error:
            msg = f"cannot encode {type(value).__name__} as JSON"
            raise CodecError(msg) from error

    @override
    def decode[T](self, data: bytes, type_: type[T], /) -> T:
        try:
            decoded: T = self._adapter(type_).validate_json(data)
        except pydantic.ValidationError as error:
            msg = f"cannot decode JSON as {type_!r}"
            raise CodecError(msg) from error
        return decoded

    def _adapter(self, type_: object) -> pydantic.TypeAdapter[Any]:
        """The TypeAdapter of type_, built once: it takes a while."""
        adapter: pydantic.TypeAdapter[Any] | None = self._adapters.get(type_)
        if adapter is None:
            try:
                adapter = pydantic.TypeAdapter(type_)  # type: ignore[arg-type]  # any type: a schema error refuses it
            except pydantic.PydanticSchemaGenerationError as error:
                msg = (
                    f"PydanticCodec cannot rebuild {type_!r}: return a model, a dataclass or a type pydantic validates"
                )
                raise InvalidOptionsError(msg) from error
            self._adapters[type_] = adapter
        return adapter
