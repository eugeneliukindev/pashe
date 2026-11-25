# Codecs

A codec turns values into bytes and back; the return annotation of a cached function says what
to rebuild.

| Codec | Where | Rebuilds |
| --- | --- | --- |
| `JsonCodec` | `pashe.codecs`, the default | what JSON holds: `dict`, `list`, `str`, numbers, `bool`, `None`; a `TypedDict` works |
| `PickleCodec(secret=...)` | `pashe.codecs` | any object pickle holds, signed with HMAC so tampered bytes are never unpickled |
| `MsgspecJsonCodec`, `MsgspecMsgpackCodec` | `pashe.contrib.msgspec` | dataclasses, msgspec `Struct`s and more, fast |
| `OrjsonCodec` | `pashe.contrib.orjson` | what JSON holds, fast |
| `PydanticCodec` | `pashe.contrib.pydantic` | pydantic models and anything a `TypeAdapter` validates |

!!! warning "A type JSON does not give back is refused when the function is decorated"

    `JsonCodec` and `OrjsonCodec` read every value back as `dict`, `list`, `str`, numbers, `bool`
    or `None`. A function that returns another type, such as a dataclass, a pydantic model, a
    `tuple` or a `set`, raises `InvalidOptionsError` at the decorator, when the app starts: its
    results would not be the type it says. Only the type itself is checked, not what a
    `list[User]` or a `User | None` holds. Give its cache `MsgspecJsonCodec` or `PydanticCodec`, which rebuild it.

=== "Sync"

    ```python
    --8<-- "codecs/codec_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "codecs/codec_async.py:show"
    ```

!!! danger "PickleCodec runs code from the backend"

    Unpickling runs code chosen by the bytes. `PickleCodec` signs every value and refuses a
    tampered one, so keep its secret out of Redis: see [Security](../../deep-dive/security.md).

## How they compare

A list of 100 products, encoded and decoded once; Python 3.15 on one machine. Your numbers will
differ, the ratios hold:

| Codec | Bytes | Encode, us | Decode, us | Rebuilds your types | Readable by other languages |
| --- | ---: | ---: | ---: | --- | --- |
| `MsgspecMsgpackCodec` | 10 178 | 19 | 42 | yes | MessagePack |
| `MsgspecJsonCodec` | 12 985 | 21 | 48 | yes | JSON |
| `OrjsonCodec` | 12 985 | 11 | 40 | no, `dict`s and `list`s | JSON |
| `JsonCodec`, the default | 12 985 | 75 | 96 | no, `dict`s and `list`s | JSON |
| `PydanticCodec` | 12 985 | 62 | 122 | yes, pydantic models | JSON |
| `PickleCodec` | 7 685 | 98 | 98 | yes, any object | no, Python only |

!!! tip "The default is the one with no dependency, not the fastest"

    `JsonCodec` needs nothing installed. For a service that caches a lot, msgspec is four times
    faster to encode and twice to decode, and gives you your dataclasses back.

!!! danger "PickleCodec"

    Unpickling runs code chosen by the bytes, so it signs every value with a secret; it is also
    the slowest. Use it only for objects no other codec holds.

---

API reference: [`pashe.codecs`](../../reference/codecs.md).
