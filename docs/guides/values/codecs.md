# Codecs

A codec turns values into bytes and back; the return annotation of a cached function says what
to rebuild.

=== "JsonCodec"

    === "Sync"

        ```python
        --8<-- "codecs/json_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/json_async.py:show"
        ```

=== "msgspec"

    === "Sync"

        ```python
        --8<-- "codecs/msgspec_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/msgspec_async.py:show"
        ```

=== "pydantic"

    === "Sync"

        ```python
        --8<-- "codecs/pydantic_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/pydantic_async.py:show"
        ```

=== "orjson"

    === "Sync"

        ```python
        --8<-- "codecs/orjson_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/orjson_async.py:show"
        ```

=== "PickleCodec"

    === "Sync"

        ```python
        --8<-- "codecs/pickle_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/pickle_async.py:show"
        ```

| Codec | Where | Rebuilds |
| --- | --- | --- |
| `JsonCodec` | `pashe.codecs`, the default | what JSON holds: `dict`, `list`, `str`, numbers, `bool`, `None`; a `TypedDict` works |
| `PickleCodec(secret=...)` | `pashe.codecs` | any object pickle holds, signed with HMAC so tampered bytes are never unpickled |
| `MsgspecJsonCodec`, `MsgspecMsgpackCodec` | `pashe.contrib.msgspec` | dataclasses, msgspec `Struct`s and more, fast |
| `OrjsonCodec` | `pashe.contrib.orjson` | what JSON holds, fast |
| `PydanticCodec` | `pashe.contrib.pydantic` | pydantic models and anything a `TypeAdapter` validates |

A codec of your own subclasses `Codec` of `pashe.codecs`: `encode` turns a value into bytes,
`decode` gives it back as the type it is asked for, and `check` refuses, when a function is
decorated, a type it cannot give back as it is; it takes every type by default.

!!! warning "A type JSON does not give back is refused when the function is decorated"

    `JsonCodec` and `OrjsonCodec` read every value back as `dict`, `list`, `str`, numbers, `bool`
    or `None`, and every key of a `dict` as `str`. A function that returns another type at any
    depth, such as a dataclass, a pydantic model, a `tuple`, a `set`, a `list[User]`, a
    `User | None` or a `dict[int, str]`, raises `InvalidOptionsError` at the decorator, when the
    app starts: its results would not be the type it says. Give its cache `MsgspecJsonCodec` or
    `PydanticCodec`, which rebuild it.

!!! danger "PickleCodec runs code from the backend"

    Unpickling runs code chosen by the bytes. `PickleCodec` signs every value and refuses a
    tampered one, so keep its secret out of Redis: see [Security](../../deep-dive/security.md).
    It is also the slowest: use it only for objects no other codec holds.

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

---

API reference: [`pashe.codecs`](../../reference/codecs.md).
