# Codecs

A backend stores bytes, so every value your cache keeps has to turn into bytes and back. That's a
codec's job. The return annotation of a cached function tells the codec which type to rebuild.
Pick a codec by what your functions return:

| Your values | The codec | Install | Rebuilds your types | Readable by other languages |
| --- | --- | --- | --- | --- |
| what JSON holds, a `TypedDict` too | [`JsonCodec`](#jsoncodec-the-default), the default | nothing | no | JSON |
| dataclasses and msgspec `Struct`s, fast | [`MsgspecMsgpackCodec`](#msgspec) | `"pashe[msgspec]"` | yes | MessagePack |
| the same, as JSON for other services | [`MsgspecJsonCodec`](#msgspec) | `"pashe[msgspec]"` | yes | JSON |
| pydantic models, anything a `TypeAdapter` takes | [`PydanticCodec`](#pydantic) | `"pashe[pydantic]"` | yes | JSON |
| what JSON holds, fast | [`OrjsonCodec`](#orjson) | `"pashe[orjson]"` | no | JSON |
| any object pickle holds, signed with HMAC | [`PickleCodec(secret=...)`](#picklecodec) | nothing | yes | no, Python only |
| a format of your own | [a `Codec` of your own](#a-codec-of-your-own) | nothing | as you write it | as you write it |

You give a codec to a cache as its [`codec`][pashe.Cache(codec)], and every value that cache
stores goes through it.

## JsonCodec, the default

A cache has to work with nothing extra installed. [`JsonCodec`][pashe.codecs.JsonCodec] stores
what JSON can hold, and a cache uses it when you don't pass `codec=`.

=== "Sync"

    ```python hl_lines="6"
    --8<-- "codecs/json_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6"
    --8<-- "codecs/json_async.py:show"
    ```

!!! warning "A type JSON can't give back fails when you decorate the function"

    `JsonCodec` and `OrjsonCodec` read every value back as `dict`, `list`, `str`, numbers, `bool`
    or `None`, and every `dict` key as `str`. Say your function returns another type anywhere
    inside: a dataclass, a pydantic model, a `tuple`, a `set`, a `list[User]`, a `User | None` or
    a `dict[int, str]`. Then the decorator raises `InvalidOptionsError` when your app starts,
    because the results wouldn't be the type the function promises. Give that cache
    `MsgspecJsonCodec` or `PydanticCodec`: they rebuild the type.

## msgspec

Does your function return dataclasses? JSON gives you `dict`s back. The codecs in
[`pashe.contrib.msgspec`][pashe.contrib.msgspec] rebuild your dataclasses, and they're fast.
[`MsgspecMsgpackCodec`][pashe.contrib.msgspec.MsgspecMsgpackCodec] stores MessagePack.
[`MsgspecJsonCodec`][pashe.contrib.msgspec.MsgspecJsonCodec] stores JSON, for when other services
read the values too.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "codecs/msgspec_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "codecs/msgspec_async.py:show"
    ```

## pydantic

If your function returns pydantic models, or anything a `TypeAdapter` validates, use
[`PydanticCodec`][pashe.contrib.pydantic.PydanticCodec]. You get them back, validated.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "codecs/pydantic_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "codecs/pydantic_async.py:show"
    ```

## orjson

If your values are plain JSON data, [`OrjsonCodec`][pashe.contrib.orjson.OrjsonCodec] encodes
and decodes them faster.

=== "Sync"

    ```python hl_lines="5"
    --8<-- "codecs/orjson_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="5"
    --8<-- "codecs/orjson_async.py:show"
    ```

It reads back the same types as `JsonCodec`, `dict`s and `list`s. So it refuses the same return
types when you decorate the function.

## PickleCodec

Some objects no other codec can store. [`PickleCodec`][pashe.codecs.PickleCodec] can. It signs
every value with HMAC under its [`secret`][pashe.codecs.PickleCodec(secret)], so it never unpickles
bytes someone tampered with.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "codecs/pickle_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "codecs/pickle_async.py:show"
    ```

!!! danger "PickleCodec runs code from the backend"

    Unpickling runs whatever code the bytes ask for. `PickleCodec` signs every value and refuses
    one that was tampered with, so keep its secret out of Redis: see
    [Security](../deep-dive/security.md). It's also the slowest to encode. Use it only for objects
    no other codec can store.

## A codec of your own

Need a format none of these writes? Subclass [`Codec`][pashe.codecs.Codec]. Its
[`validate`][pashe.codecs.Codec.validate] refuses a type it can't give back, right when you
decorate the function. Without it, you only find a wrong type when a value is read.

## How they compare

For what each one costs in bytes and microseconds, see
[Benchmarks](../deep-dive/benchmarks.md#codecs).

!!! tip "The default is the one with no dependency, not the fastest"

    `JsonCodec` needs nothing installed. If your service caches a lot, msgspec is almost four
    times faster to encode and twice as fast to decode. It also gives you your dataclasses back.
