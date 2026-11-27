from __future__ import annotations

import inspect
import re
import types
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Final,
    Literal,
    NewType,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

from pashe.errors import InvalidOptionsError, WrongTypeError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from pashe.options import Duration

# What a user gives is checked here, once, where it comes in. expect_* checks and returns None;
# parse_* checks and returns the value in the form the code inside trusts, such as seconds. A check
# that the lines after it rely on uses isinstance itself, which the type checkers see, and type_error.
__all__ = [
    "DURATION",
    "FUNCTION",
    "duration_seconds",
    "expect_error_classes",
    "expect_int64",
    "expect_item_types",
    "expect_json_type",
    "expect_positive",
    "expect_type",
    "is_async",
    "parse_int",
    "parse_seconds",
    "parse_secret",
    "parse_timeout",
    "parse_ttl",
    "type_error",
]

DURATION: Final = int | float | timedelta  # what isinstance checks a Duration as
_NUMBER: Final = int | float

# isinstance takes Callable for any function, while the type checkers see a special form, not a type.
FUNCTION: Final[type] = Callable  # type: ignore[assignment]

_MIN_SECRET: Final = 16  # bytes of a secret, as every HMAC-SHA256 of pashe takes it
_INT64_MIN: Final = -0x8000000000000000
_INT64_MAX: Final = 0x7FFFFFFFFFFFFFFF
_DECIMAL: Final = re.compile(rb"0|-?[1-9][0-9]*")  # a counter as Redis takes it: no leading 0, no -0

# Any and object promise no type, so whatever JSON gives back is it.
_JSON_TYPES: Final = frozenset((dict, list, str, int, float, bool, types.NoneType, Any, object))
_JSON_VALUES: Final = (dict, list, str, int, float, bool, types.NoneType)  # what json reads back
_JSON_KEYS: Final = frozenset((str, Any, object))  # JSON writes every key of an object as str
_UNIONS: Final = (types.UnionType, Union)  # the origins of X | Y and of Optional[X] before 3.14


def expect_type(
    name: str,
    value: object,
    kind: type | types.UnionType,
) -> None:
    """``kind`` is a class or a union of classes as isinstance takes it, such as str | None."""
    if not isinstance(value, kind):
        raise type_error(name, value, kind)


def type_error(
    name: str,
    value: object,
    kind: type | types.UnionType,
) -> TypeError:
    """The error of a value that is not of kind, for the caller to raise."""
    names = " or ".join(_name(member) for member in get_args(kind) or (kind,))
    return TypeError(f"{name} must be {names}, not {type(value).__name__}")


def expect_item_types(
    name: str,
    values: Iterable[object],
    kind: type | types.UnionType,
) -> None:
    for index, value in enumerate(values):
        expect_type(f"{name}[{index}]", value, kind)


def expect_error_classes(name: str, values: object) -> None:
    if not isinstance(values, tuple):
        raise type_error(name, values, tuple)
    errors: tuple[object, ...] = values  # pyright: ignore[reportUnknownVariableType] - isinstance leaves the items unknown
    for index, value in enumerate(errors):
        if not (isinstance(value, type) and issubclass(value, Exception)):
            msg = f"{name}[{index}] must be a class of exceptions, such as ValueError, not {value!r}"
            raise TypeError(msg)


def expect_positive(
    name: str,
    value: object,
    meaning: str,
) -> None:
    """A number more than 0; an int with a bound is parse_int."""
    if not isinstance(value, int | float):
        raise type_error(name, value, _NUMBER)
    if not value > 0:
        msg = f"{name} is {value}: {meaning}"
        raise InvalidOptionsError(msg)


def expect_int64(name: str, value: int) -> None:
    """The counters of every backend are signed 64-bit integers, as Redis keeps them."""
    if not _INT64_MIN <= value <= _INT64_MAX:
        msg = f"{name} is {value}: out of the signed 64-bit range of a counter"
        raise OverflowError(msg)


def parse_counter(backend_name: str, data: bytes) -> int:
    """The integer incr keeps, as ASCII decimal: any other value is not a counter."""
    if _DECIMAL.fullmatch(data) is None:
        msg = f"{backend_name}: value is not an integer"
        raise WrongTypeError(msg)
    parsed = int(data)
    try:
        expect_int64(f"{backend_name}.value", parsed)
    except OverflowError as error:  # a value out of the range is not a counter
        raise WrongTypeError(str(error)) from error
    return parsed


def _type_parts(form: object) -> Iterator[object]:  # noqa: WPS231 - one walk through every kind of type
    """Every type a value of form is made of, form first, each once.

    What an alias or a NewType stands for, the arguments of a generic and the fields of
    a class. A Literal holds values and Annotated metadata, not types; a class whose
    annotations name what is not defined has no parts.
    """
    seen: dict[int, object] = {}  # by id, as an argument such as the [int] of Callable[[int], str] has no hash
    stack = [form]
    while stack:
        part = stack.pop()
        if id(part) in seen:
            continue
        seen[id(part)] = part  # kept, so its id is not reused while the walk lasts
        if isinstance(part, TypeAliasType | NewType):  # in place of what it stands for
            stack.append(part.__value__ if isinstance(part, TypeAliasType) else part.__supertype__)
            continue

        yield part
        origin = get_origin(part)
        if origin is Annotated:
            stack.append(get_args(part)[0])
        elif origin is not None and origin is not Literal:
            stack.extend(get_args(part))
        elif inspect.isclass(part):
            try:
                hints = get_type_hints(part)
            except (NameError, TypeError):
                continue
            # a field of data, not one of the class itself, such as __pydantic_extra__ or a ClassVar
            stack.extend(
                hint for name, hint in hints.items() if not name.startswith("__") and get_origin(hint) is not ClassVar
            )


def expect_json_type(codec_name: str, form: object) -> None:  # noqa: WPS231 - every part of the type, and the keys of its dicts
    """Refuse a type with a part a codec of JSON would read back as another one.

    JSON gives back dict, list, str, numbers, bool and None, so at any depth a dataclass,
    a tuple, or a dict of int keys, which JSON writes as str, is refused. Any and object
    promise no type: whatever comes back is it.
    """
    for part in _type_parts(form):
        origin = get_origin(part)
        kind = part if origin is None else origin
        if origin in _UNIONS or not inspect.isclass(kind) or is_typeddict(kind):  # by their parts; a Literal, a TypeVar
            continue
        # a class one of them is, such as Sequence, which a list is
        if kind not in _JSON_TYPES and not any(issubclass(read, kind) for read in _JSON_VALUES):  # pyrefly: ignore[implicit-any-type-argument] - issubclass takes the classes bare
            msg = (
                f"{codec_name} reads {kind.__name__} back as another type: return dict, list, str, numbers,"
                " bool or None, or give the cache MsgspecJsonCodec or PydanticCodec, which rebuild it"
            )
            raise InvalidOptionsError(msg)

        arguments = get_args(part)
        key = next(_type_parts(arguments[0])) if issubclass(kind, Mapping) and arguments else str
        if inspect.isclass(key) and key not in _JSON_KEYS:
            msg = (
                f"{codec_name} reads the keys of {part!r} back as str: key it by str, or give the cache"
                " MsgspecJsonCodec or PydanticCodec, which rebuild it"
            )
            raise InvalidOptionsError(msg)


def parse_secret(name: str, secret: object) -> bytes:
    """A key of HMAC-SHA256, as bytes: shorter than 16 it is too easy to guess."""
    if not isinstance(secret, str | bytes):
        raise type_error(name, secret, str | bytes)
    key = secret.encode() if isinstance(secret, str) else secret
    if len(key) < _MIN_SECRET:
        msg = f"{name} needs at least {_MIN_SECRET} bytes"
        raise InvalidOptionsError(msg)
    return key


def parse_seconds(
    name: str,
    value: object,
    meaning: str,
    *,
    positive: bool = False,
) -> float:
    """A duration as seconds, 0 or more, or with positive more than 0; meaning says what it is for."""
    seconds = _seconds(value)
    if seconds is None:
        raise type_error(name, value, DURATION)
    if seconds < 0 or (positive and not seconds):
        bound = "more than 0" if positive else "0 or more"
        msg = f"{name} is {value!r}: {meaning}, {bound} seconds"
        raise InvalidOptionsError(msg)
    return seconds


def parse_timeout(
    name: str,
    value: object,
    meaning: str,
) -> float | None:
    """The most to wait; None waits as long as it takes."""
    return None if value is None else parse_seconds(name, value, meaning)


def parse_ttl(
    name: str,
    value: object,
    meaning: str,
) -> float | Callable[[Any], Duration]:
    """How long a result is fresh: a duration, or a function of the result that returns one."""
    if callable(value):
        return value  # pyright: ignore[reportReturnType]  # its result is checked when it returns one
    try:
        return parse_seconds(name, value, meaning)
    except TypeError:  # a ttl may be a function too, which the error names
        raise type_error(name, value, DURATION | FUNCTION) from None


def parse_int(
    name: str,
    value: object,
    *,
    low: int,
    high: int | None = None,
    meaning: str,
) -> int:
    """An int from low to high; with no high, any from low up."""
    if not isinstance(value, int):
        raise type_error(name, value, int)
    if value < low or (high is not None and value > high):
        msg = f"{name} is {value}: {meaning}"
        raise InvalidOptionsError(msg)
    return value


def duration_seconds(duration: Duration, /) -> float:
    """Return a duration as the options take it, seconds or a timedelta, in seconds.

    Args:
        duration: seconds, or a timedelta.

    Returns:
        The seconds.

    Raises:
        TypeError: an argument is not of the type its annotation names.

    Examples:
        >>> from datetime import timedelta
        >>> from pashe.options import duration_seconds
        >>> duration_seconds(timedelta(minutes=1)), duration_seconds(30)
        (60.0, 30.0)
    """
    seconds = _seconds(duration)
    if seconds is None:
        raise type_error("duration", duration, DURATION)  # noqa: EM101 - the name of the argument, not a message
    return seconds


def _seconds(duration: object) -> float | None:
    """A duration in seconds, None for what is not one."""
    if isinstance(duration, timedelta):
        return duration.total_seconds()
    if isinstance(duration, int | float):
        return float(duration)
    return None


def is_async(function: Callable[..., object]) -> bool:
    return inspect.iscoroutinefunction(function) or inspect.iscoroutinefunction(type(function).__call__)


def _name(kind: object) -> str:
    if kind is types.NoneType:
        return "None"
    if kind is FUNCTION:
        return "a function"
    return kind.__name__ if isinstance(kind, type) else repr(kind)
