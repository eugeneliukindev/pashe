# Codecs

A codec turns values into bytes and back; the return annotation of a cached function says what
to rebuild. Pick the codec by what your functions return:

| Your values | The codec | Install | Rebuilds your types | Readable by other languages |
| --- | --- | --- | --- | --- |
| what JSON holds, a `TypedDict` too | [`JsonCodec`](#jsoncodec-the-default), the default | nothing | no | JSON |
| dataclasses and msgspec `Struct`s, fast | [`MsgspecMsgpackCodec`](#msgspec) | `"pashe[msgspec]"` | yes | MessagePack |
| the same, as JSON for other services | [`MsgspecJsonCodec`](#msgspec) | `"pashe[msgspec]"` | yes | JSON |
| pydantic models, anything a `TypeAdapter` takes | [`PydanticCodec`](#pydantic) | `"pashe[pydantic]"` | yes | JSON |
| what JSON holds, fast | [`OrjsonCodec`](#orjson) | `"pashe[orjson]"` | no | JSON |
| any object pickle holds, signed with HMAC | [`PickleCodec(secret=...)`](#picklecodec) | nothing | yes | no, Python only |
| a format of your own | [a `Codec` of your own](#a-codec-of-your-own) | nothing | as you write it | as you write it |

A codec belongs to a cache, as its [`codec`][pashe.Cache(codec)], and every value the cache
stores goes through it.

## JsonCodec, the default

A cache needs a format for its values with nothing installed;
[`JsonCodec`][pashe.codecs.JsonCodec] holds what JSON holds, and a cache without `codec=` takes it.

=== "Sync"

    ```python hl_lines="6"
    --8<-- "codecs/json_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6"
    --8<-- "codecs/json_async.py:show"
    ```

!!! warning "A type JSON does not give back is refused when the function is decorated"

    `JsonCodec` and `OrjsonCodec` read every value back as `dict`, `list`, `str`, numbers, `bool`
    or `None`, and every key of a `dict` as `str`. A function that returns another type at any
    depth, such as a dataclass, a pydantic model, a `tuple`, a `set`, a `list[User]`, a
    `User | None` or a `dict[int, str]`, raises `InvalidOptionsError` at the decorator, when the
    app starts: its results would not be the type it says. Give its cache `MsgspecJsonCodec` or
    `PydanticCodec`, which rebuild it.

## msgspec

A function that returns dataclasses gets `dict`s back from JSON; the codecs of
[`pashe.contrib.msgspec`][pashe.contrib.msgspec] rebuild them, fast:
[`MsgspecMsgpackCodec`][pashe.contrib.msgspec.MsgspecMsgpackCodec] stores MessagePack, and
[`MsgspecJsonCodec`][pashe.contrib.msgspec.MsgspecJsonCodec] JSON, for other services that read
the values.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "codecs/msgspec_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "codecs/msgspec_async.py:show"
    ```

## pydantic

A function that returns pydantic models, or anything a `TypeAdapter` validates, gets them back,
validated, with [`PydanticCodec`][pashe.contrib.pydantic.PydanticCodec].

=== "Sync"

    ```python hl_lines="7"
    --8<-- "codecs/pydantic_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "codecs/pydantic_async.py:show"
    ```

## orjson

Values that are what JSON holds encode and decode faster with
[`OrjsonCodec`][pashe.contrib.orjson.OrjsonCodec].

=== "Sync"

    ```python hl_lines="5"
    --8<-- "codecs/orjson_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="5"
    --8<-- "codecs/orjson_async.py:show"
    ```

It reads back the same types as `JsonCodec`, `dict`s and `list`s, so it refuses the same return
types when the function is decorated.

## PickleCodec

An object no other codec holds is stored by [`PickleCodec`][pashe.codecs.PickleCodec], which
signs every value with HMAC under its [`secret`][pashe.codecs.PickleCodec(secret)], so tampered
bytes are never unpickled.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "codecs/pickle_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "codecs/pickle_async.py:show"
    ```

!!! danger "PickleCodec runs code from the backend"

    Unpickling runs code chosen by the bytes. `PickleCodec` signs every value and refuses a
    tampered one, so keep its secret out of Redis: see [Security](../deep-dive/security.md).
    It is also the slowest to encode: use it only for objects no other codec holds.

## A codec of your own

For a format none of these writes, subclass [`Codec`][pashe.codecs.Codec].
[`validate`][pashe.codecs.Codec.validate] is where it refuses, when a function is decorated, a
type it cannot give back: without it a wrong type shows up only when a value is read.

## How they compare

What each one costs in bytes and microseconds: [Benchmarks](../deep-dive/benchmarks.md#codecs).

!!! tip "The default is the one with no dependency, not the fastest"

    `JsonCodec` needs nothing installed. For a service that caches a lot, msgspec is almost four
    times faster to encode and twice to decode, and gives you your dataclasses back.
