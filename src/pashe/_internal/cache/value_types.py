from __future__ import annotations

import enum
import functools
import hashlib
import inspect
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar, Final, NewType, TypeAliasType, get_args, get_origin, get_type_hints

from pashe.errors import InvalidOptionsError

if TYPE_CHECKING:
    from collections.abc import Callable

_SHAPE_BYTES: Final = 8
_MAPPING_ARGUMENTS: Final = 2  # dict[K, V]


def return_type(function: Callable[..., object]) -> object:
    """Read once, when the function is decorated: every name its annotations use must be defined by then."""
    try:
        hints = get_type_hints(function)
    except NameError as error:
        name = _name(function)
        msg = (
            f"{name} is annotated with {error.name}, which is not defined yet: define or import it above {name};"
            " a method that returns its own class takes the decorator after the class, as Node.load = cache(...)(Node.load)"
        )
        raise InvalidOptionsError(msg) from error
    return hints.get("return", Any)


def batch_value_type(function: Callable[..., object]) -> object:
    """A batch stores every value of the dict it returns on its own, so the codec rebuilds V of dict[K, V]."""
    form = return_type(function)
    if form is Any:
        return Any

    origin = get_origin(form) or form
    if not (isinstance(origin, type) and issubclass(origin, Mapping)):
        msg = f"{_name(function)} must return dict[K, V], not {_name(form)}"
        raise InvalidOptionsError(msg)

    arguments = get_args(form)
    return arguments[1] if len(arguments) == _MAPPING_ARGUMENTS else Any


@functools.cache
def fingerprint(form: object) -> int:
    digest = hashlib.blake2b(_describe(form, frozenset()).encode(), digest_size=_SHAPE_BYTES).digest()
    return int.from_bytes(digest)


def _name(form: object) -> str:
    """A function or a class by its name; a generic, such as list[int], as it is written."""
    return getattr(form, "__qualname__", repr(form)) if get_origin(form) is None else repr(form)


def _describe(form: object, seen: frozenset[object]) -> str:  # noqa: PLR0911, WPS212 - one return for each kind of type
    """What a type alias or a NewType stands for counts: a value of the alias changed is another shape."""
    if isinstance(form, TypeAliasType):
        return form.__name__ if form in seen else _describe(form.__value__, seen | {form})
    if isinstance(form, NewType):
        return f"{form.__name__}<{_describe(form.__supertype__, seen)}>"
    origin = get_origin(form)
    if origin is not None:
        arguments = ",".join(_describe(argument, seen) for argument in get_args(form))
        return f"{_describe(origin, seen)}[{arguments}]"
    if not inspect.isclass(form):
        return repr(form)  # a Literal value, a TypeVar

    name = f"{form.__module__}.{form.__qualname__}"
    if form in seen:
        return name
    if issubclass(form, enum.Enum):
        return name + repr([member.value for member in form])

    try:
        hints = get_type_hints(form)
    except NameError:
        return name  # a name its annotations use cannot be resolved: the class is known by its name alone

    inner = seen | {form}
    fields = ",".join(
        f"{field}:{_describe(hint, inner)}" for field, hint in hints.items() if get_origin(hint) is not ClassVar
    )
    return f"{name}{{{fields}}}" if fields else name
