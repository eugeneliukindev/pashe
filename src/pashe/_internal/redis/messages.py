from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, NamedTuple, final

if TYPE_CHECKING:
    from collections.abc import Sequence

_KEYS: Final = "keys"
_MESSAGE: Final = b"message"
_MESSAGE_PARTS: Final = 3  # "message", the channel, the keys


@final
class Invalidation(NamedTuple):
    # what read_invalidation made of a reply on the tracking connection
    tracked: bool  # a message of tracking, not the reply to a command
    keys: list[str] | None  # the keys it names; None for every key, or for one pashe cannot read


def encode_message(keys: Sequence[str] | None) -> str:
    return json.dumps({_KEYS: keys and list(keys)})


def decode_message(data: object) -> list[str] | None:
    """The keys of a message.

    None for every key, and for a message pashe cannot read, which drops every copy. A
    message of an older pashe also names its sender: it is not read.
    """
    try:
        decoded: object = json.loads(data)  # type: ignore[arg-type]  # a message of another type raises TypeError
    except (TypeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    fields: dict[object, object] = decoded  # pyright: ignore[reportUnknownVariableType] - isinstance leaves the fields unknown
    items = fields.get(_KEYS)
    if not isinstance(items, list):
        return None
    listed: list[object] = items  # pyright: ignore[reportUnknownVariableType] - as above
    if not all(isinstance(key, str) for key in listed):
        return None
    return listed  # type: ignore[return-value]  # every item a str: just checked


def read_invalidation(received: object) -> Invalidation:
    """Whether a reply on the tracking connection is a message of tracking, and its keys.

    None for every key, as after FLUSHALL, and for a message pashe cannot read, which
    drops every copy.
    """
    if not isinstance(received, list):
        return Invalidation(tracked=False, keys=None)

    items: list[object] = received  # pyright: ignore[reportUnknownVariableType] - isinstance leaves the items unknown
    if not items or items[0] != _MESSAGE:
        return Invalidation(tracked=False, keys=None)  # the reply to a command, such as to SUBSCRIBE
    if len(items) != _MESSAGE_PARTS or not isinstance(items[2], list):
        return Invalidation(tracked=True, keys=None)

    keys: list[object] = items[2]  # pyright: ignore[reportUnknownVariableType] - as above
    decoded = [key.decode(errors="replace") for key in keys if isinstance(key, bytes)]
    return Invalidation(tracked=True, keys=decoded if len(decoded) == len(keys) else None)
