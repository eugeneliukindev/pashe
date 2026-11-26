from __future__ import annotations

import inspect
import re
import types
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, NewType, TypeAliasType, get_args, get_origin, is_typeddict

from pashe.errors import InvalidOptionsError, WrongTypeError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pashe.options import Duration

# What a user gives is checked here, once, where it comes in. expect_* checks and returns None;
# parse_* checks and returns the value in the form the code inside trusts, such as seconds.
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


def expect_type(
    name: str,
    value: object,
    kind: type | types.UnionType,
) -> None:
    # kind is a class or a union of classes as isinstance takes it, such as str | None
    if isinstance(value, kind):
        return
    names = " or ".join(_name(member) for member in get_args(kind) or (kind,))
    msg = f"{name} must be {names}, not {type(value).__name__}"
    raise TypeError(msg)


def expect_item_types(
    name: str,
    values: Iterable[object],
    kind: type | types.UnionType,
) -> None:
    for index, value in enumerate(values):
        expect_type(f"{name}[{index}]", value, kind)


def expect_error_classes(name: str, values: object) -> None:
    expect_type(name, values, tuple)
    errors: tuple[object, ...] = values  # type: ignore[assignment]  # a tuple: expect_type just checked it
    for index, value in enumerate(errors):
        if not (isinstance(value, type) and issubclass(value, Exception)):
            msg = f"{name}[{index}] must be a class of exceptions, such as ValueError, not {value!r}"
            raise TypeError(msg)


def expect_positive(
    name: str,
    value: object,
    meaning: str,
    *,
    kind: type | types.UnionType = _NUMBER,
) -> None:
    expect_type(name, value, kind)
    if not value > 0:  # type: ignore[operator]  # a number: expect_type just checked it
        msg = f"{name} is {value}: {meaning}"
        raise InvalidOptionsError(msg)


def expect_int64(name: str, value: int) -> None:
    # the counters of every backend are signed 64-bit integers, as Redis keeps them
    if not _INT64_MIN <= value <= _INT64_MAX:
        msg = f"{name} is {value}: out of the signed 64-bit range of a counter"
        raise OverflowError(msg)


def parse_counter(backend_name: str, data: bytes) -> int:
    # the integer incr keeps, as ASCII decimal: any other value is not a counter
    if _DECIMAL.fullmatch(data) is None:
        msg = f"{backend_name}: value is not an integer"
        raise WrongTypeError(msg)
    parsed = int(data)
    try:
        expect_int64(f"{backend_name}.value", parsed)
    except OverflowError as error:  # a value out of the range is not a counter
        raise WrongTypeError(str(error)) from error
    return parsed


def expect_json_type(codec_name: str, form: object) -> None:
    # A codec of JSON gives back dict, list, str, numbers, bool and None: refuse a class it would
    # read back as one of them, such as a dataclass, a model, or the tuple of tuple[int, int]. What
    # a generic or a union holds is not looked into.
    while isinstance(form, TypeAliasType | NewType):  # what the alias stands for
        form = form.__value__ if isinstance(form, TypeAliasType) else form.__supertype__

    kind = get_origin(form) or form
    if not isinstance(kind, type) or kind in _JSON_TYPES or kind is types.UnionType or is_typeddict(kind):
        return
    # a class one of them is, such as Sequence, which a list is
    if any(issubclass(read, kind) for read in _JSON_VALUES):  # pyrefly: ignore[implicit-any-type-argument] - issubclass takes the classes bare
        return

    msg = (
        f"{codec_name} reads {kind.__name__} back as another type: return dict, list, str, numbers, bool"
        " or None, or give the cache MsgspecJsonCodec or PydanticCodec, which rebuild it"
    )
    raise InvalidOptionsError(msg)


def parse_secret(name: str, secret: object) -> bytes:
    # a key of HMAC-SHA256, as bytes: shorter than 16 it is too easy to guess
    expect_type(name, secret, str | bytes)
    key = secret.encode() if isinstance(secret, str) else secret
    if len(key) < _MIN_SECRET:  # type: ignore[arg-type]  # bytes: expect_type just checked it
        msg = f"{name} needs at least {_MIN_SECRET} bytes"
        raise InvalidOptionsError(msg)
    return key  # type: ignore[return-value]  # as above


def parse_seconds(
    name: str,
    value: object,
    meaning: str,
    *,
    positive: bool = False,
) -> float:
    # a duration as seconds, 0 or more, or with positive more than 0; meaning says what it is for
    expect_type(name, value, DURATION)
    seconds = duration_seconds(value)  # type: ignore[arg-type]  # a Duration: expect_type just checked it
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
    # the most to wait; None waits as long as it takes
    return None if value is None else parse_seconds(name, value, meaning)


def parse_ttl(
    name: str,
    value: object,
    meaning: str,
) -> float | Callable[[Any], Duration]:
    # how long a result is fresh: a duration, or a function of the result that returns one
    expect_type(name, value, DURATION | FUNCTION)
    if callable(value):
        return value  # pyright: ignore[reportReturnType]  # its result is checked when it returns one
    return parse_seconds(name, value, meaning)


def parse_int(
    name: str,
    value: object,
    *,
    low: int,
    high: int | None = None,
    meaning: str,
) -> int:
    # an int from low to high; with no high, any from low up
    expect_type(name, value, int)
    number: int = value  # type: ignore[assignment]  # an int: expect_type just checked it
    if number < low or (high is not None and number > high):
        msg = f"{name} is {number}: {meaning}"
        raise InvalidOptionsError(msg)
    return number


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
    expect_type("duration", duration, DURATION)
    return duration.total_seconds() if isinstance(duration, timedelta) else float(duration)


def is_async(function: Callable[..., object]) -> bool:
    return inspect.iscoroutinefunction(function) or inspect.iscoroutinefunction(type(function).__call__)


def _name(kind: object) -> str:
    if kind is types.NoneType:
        return "None"
    if kind is FUNCTION:
        return "a function"
    return kind.__name__ if isinstance(kind, type) else repr(kind)
