from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import enum
import hashlib
import hmac
import inspect
import itertools
import json
import string
import uuid
from typing import TYPE_CHECKING, Final, NamedTuple, final, override

from pashe.errors import InvalidOptionsError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_DIGEST_BYTES: Final = 16  # 128 bits: no two values of a cache collide in practice
_BLAKE2B: Final = "blake2b"  # fast
_SHA256: Final = "sha256"  # for where only FIPS algorithms are allowed
_HMAC: Final = "hmac"  # HMAC-SHA256 under the secret of the cache
_DIGESTS: Final = frozenset((_BLAKE2B, _SHA256, _HMAC))
_COMPACT: Final = (",", ":")
# The text of these is stable: no address of an object, no order of a set.
_STABLE_TYPES: Final = (str, int, float, bool, type(None), dt.date, dt.time, uuid.UUID, decimal.Decimal)
_BOUND_NAMES: Final = frozenset(("self", "cls"))
_LOCALS: Final = "<locals>"  # what a qualified name has for a function defined in a function
_LAMBDA: Final = "<lambda>"  # the qualified name of every lambda

type _Parsed = tuple[str, str | None, str | None, str | None]  # what Formatter.parse gives a part


@final
class KeyBuilder:
    __slots__ = ("_bound", "_name", "_positional", "_signature", "_tags", "_template")

    def __init__(
        self, function: Callable[..., object], template: KeyTemplate | None, tags: Sequence[KeyTemplate]
    ) -> None:
        self._signature = inspect.signature(function)

        kinds = [parameter.kind for parameter in self._signature.parameters.values()]
        plain = all(kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for kind in kinds)

        # the names of the parameters when a call that gives each by position binds them in order
        self._positional = tuple(self._signature.parameters) if plain else None
        self._name = qualified_name(function)
        for checked in (*tags, *(() if template is None else (template,))):
            unknown = sorted(checked.names - self._signature.parameters.keys())
            if unknown:
                msg = f"{checked} names {{{unknown[0]}}}: {self._name} has no such parameter"
                raise InvalidOptionsError(msg)

        # self or cls of a method: apart from the key, so every instance shares the results
        owner = function.__qualname__.rpartition(".")[0]
        first = next(iter(self._signature.parameters), None)
        in_class = bool(owner) and not owner.endswith(_LOCALS)

        self._bound = first if in_class and first in _BOUND_NAMES else None

        self._template = template
        self._tags = tuple(tags)

    def key(self, args: Sequence[object], kwargs: Mapping[str, object]) -> str:
        return self._key(self._arguments(args, kwargs))

    def key_and_tags(self, args: Sequence[object], kwargs: Mapping[str, object]) -> KeyAndTags:
        arguments = self._arguments(args, kwargs)
        return KeyAndTags(self._key(arguments), self._tags_of(arguments))

    def tags(self, args: Sequence[object], kwargs: Mapping[str, object]) -> tuple[str, ...]:
        return self._tags_of(self._arguments(args, kwargs))

    def _key(self, arguments: Mapping[str, object]) -> str:
        if self._template is not None:
            return self._template.render((), arguments)
        parts = [_part(name, value) for name, value in arguments.items() if name != self._bound]
        return ":".join([self._name, *parts])

    def _tags_of(self, arguments: Mapping[str, object]) -> tuple[str, ...]:
        return tuple(tag.render((), arguments) for tag in self._tags)

    def _arguments(self, args: Sequence[object], kwargs: Mapping[str, object]) -> dict[str, object]:
        if self._positional is not None and not kwargs and len(args) == len(self._positional):
            return dict(zip(self._positional, args, strict=True))  # what bind makes of it, at a fraction of its cost
        bound = self._signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return bound.arguments


@final
class KeyAndTags(NamedTuple):
    # what the arguments of a call make: its key, and its tags filled in
    key: str
    tags: tuple[str, ...]


@final
class KeyTemplate:
    # a str.format template of a key or a tag, checked when it is made: only a checked one renders
    __slots__ = ("_fields", "_parts", "_text", "names")

    def __init__(self, text: str, *, secret: bytes | None) -> None:
        # secret: the key_secret of the cache, for {name:hmac}
        fields = _KeyFormatter(secret)
        names: set[str] = set()
        parsed = list(fields.parse(text))
        for _, field, spec, _ in parsed:
            if field is None:
                continue
            names.add(field.partition(".")[0].partition("[")[0])  # {user.id} names user
            if spec:
                fields.check_spec(text, spec)
        self._text = text

        self._fields = fields
        self._parts = self._precompile(parsed)
        self.names: frozenset[str] = frozenset(names)

    def render(self, args: Sequence[object], kwargs: Mapping[str, object]) -> str:
        if self._parts is None:
            return self._fields.vformat(self._text, args, kwargs)
        rendered: list[str] = []
        for literal, field, spec, conversion in self._parts:
            rendered.append(literal)
            if field is not None:
                value = self._fields.get_field(field, args, kwargs)[0]
                rendered.append(self._fields.format_field(self._fields.convert_field(value, conversion), spec or ""))
        return "".join(rendered)

    @override
    def __str__(self) -> str:
        return repr(self._text)

    def _precompile(self, parsed: list[_Parsed]) -> list[_Parsed] | None:
        # The template as Formatter.vformat reads it on every call, read once: a field {} numbered as
        # vformat numbers it. None leaves the rare template to vformat: a field inside a spec, or {}
        # mixed with numbered fields, which vformat refuses.
        if any(spec and "{" in spec for _, _, spec, _ in parsed):
            return None
        fields = [field for _, field, _, _ in parsed if field is not None]
        if "" in fields and any(field[:1].isdigit() for field in fields):
            return None
        numbers = itertools.count()
        return [
            (literal, str(next(numbers)) if field == "" else field, spec, conversion)
            for literal, field, spec, conversion in parsed
        ]


@final
@enum.unique
class KeyPrefix(enum.StrEnum):
    # What the cache puts before a key of its own, under the prefix of the cache. The values are
    # the format of keys already in backends: renaming a member is fine, changing a value is not.
    TAG = "__tag:"  # the generation counter of a tag
    STAMPEDE_LOCK = "__stampede:"  # the Stampede.lock_for lock of an entry
    REVALIDATION_LOCK = "__revalidation:"  # the lock of the one revalidation of an entry
    LOCK = "__lock:"  # a lock of cache.lock, try_lock and locked
    SLIDING_WINDOW = "__rate:sliding:"  # the counters of a SlidingWindow
    FIXED_WINDOW = "__rate:fixed:"  # the counter of a FixedWindow


def item_key(name: str, template: KeyTemplate | None, item: object) -> str:
    if template is not None:
        return template.render((item,), {})
    return f"{name}:{_part('item', item)}"


def qualified_name(function: Callable[..., object]) -> str:
    name = getattr(function, "__qualname__", None)
    if name is None:
        msg = f"{function!r} has no name for its keys: decorate a def that calls it"
        raise TypeError(msg)
    return f"{function.__module__}.{name}"


def key_name(function: Callable[..., object]) -> str:
    # the qualified name a key starts with when no template names it: a lambda has none of its own
    name = qualified_name(function)
    if name.endswith(_LAMBDA):
        msg = f"{name} is a lambda, and every lambda of its module would share its keys: pass key="
        raise InvalidOptionsError(msg)
    return name


def canonical(value: object) -> bytes:
    try:
        text = _CANONICAL.encode(value)
    except (TypeError, ValueError) as error:
        msg = f"cannot hash a {type(value).__name__} into a key: {error}"
        raise TypeError(msg) from error
    return text.encode()


def has_stable_text(value: object) -> bool:
    plain = value.value if isinstance(value, enum.Enum) else value
    return isinstance(plain, _STABLE_TYPES)


@final
class _KeyFormatter(string.Formatter):
    # formats the fields of the keys of one cache, with its key_secret for hmac: digests, and the
    # text of a value only when it is stable

    def __init__(self, secret: bytes | None) -> None:
        super().__init__()

        self._secret = secret

    @override
    def format_field(self, value: object, format_spec: str) -> str:
        if format_spec == _BLAKE2B:
            return hashlib.blake2b(canonical(value), digest_size=_DIGEST_BYTES).hexdigest()
        if format_spec == _SHA256:
            return hashlib.sha256(canonical(value)).digest()[:_DIGEST_BYTES].hex()
        if format_spec == _HMAC and self._secret is not None:
            return hmac.digest(self._secret, canonical(value), _SHA256)[:_DIGEST_BYTES].hex()
        if not has_stable_text(value):
            msg = (
                f"a value of {type(value).__name__} has no stable text for a key: name a plain part of it,"
                " such as {user.id}, or hash it, such as {user:blake2b}"
            )
            raise TypeError(msg)
        return str(super().format_field(value, format_spec))

    def check_spec(self, template: str, spec: str) -> None:
        if spec == _HMAC and self._secret is None:
            msg = f"{template!r} uses hmac: give the cache a key_secret"
            raise InvalidOptionsError(msg)
        if spec not in _DIGESTS and spec.isidentifier() and len(spec) > 1:
            msg = f"{template!r} uses {spec!r}: the digests are blake2b, sha256 and hmac"
            raise InvalidOptionsError(msg)


def _part(name: str, value: object) -> str:
    if not has_stable_text(value):
        field = "" if name == "item" else name
        msg = (
            f"argument {name!r} is a {type(value).__name__}: pass key= with a template to name it,"
            f' or to hash it, such as "{{{field}:blake2b}}"'
        )
        raise TypeError(msg)
    if isinstance(value, enum.Enum):
        return f"{type(value).__qualname__}.{value.name}"  # apart from its value, which another argument may be
    return repr(value)


def _plain(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # one level: json walks the rest, so a cycle, as of relationships, raises instead of recursing
        return {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, decimal.Decimal)):
        return str(value)
    if isinstance(value, (set, frozenset)):
        # members of any type, sorted by their JSON; isinstance leaves their type unknown to pyright
        return sorted(value, key=canonical)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    msg = f"{type(value).__name__} has no canonical form: give the template a plain part of it"
    raise TypeError(msg)


# one encoder for every key, as json.dumps with options builds a new one on each call; after _plain, which it calls
_CANONICAL: Final = json.JSONEncoder(
    sort_keys=True, separators=_COMPACT, ensure_ascii=False, allow_nan=False, default=_plain
)
