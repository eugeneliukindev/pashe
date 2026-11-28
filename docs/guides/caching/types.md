# Types

A cached function has the same type as the function it caches. Your type checker sees the same
parameters and the same result. A stored result comes back as its type when the codec can rebuild
it. The default codec, [`JsonCodec`][pashe.codecs.JsonCodec], gives back what JSON holds, so a
`TypedDict` works as it is.

=== "Sync"

    ```python
    --8<-- "caching_functions/types_sync.py:show"
    --8<-- "caching_functions/types_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/types_async.py:show"
    --8<-- "caching_functions/types_async.py:calls"
    ```

## What a result decodes as

Your function's return annotation tells pashe what type to decode a stored result as. For a batch,
it's the type of the values in the `dict` it returns. The codec does the decoding, so the codec
decides which types come back whole. [Codecs](../codecs.md) lists them.

What if the codec would give your type back as something else? Then pashe refuses it when you
decorate the function, not when it first reads a result. For example, a dataclass under
`JsonCodec` raises [`InvalidOptionsError`][pashe.errors.InvalidOptionsError], and the error names
the codecs that can rebuild it.

A type the codec accepts comes back as it went in. So a miss returns the result your function
returned, and a hit returns the same thing. If your function has no return annotation, or part of
its type is `Any`, a hit gets whatever the codec reads on its own: for example, a list instead of a
tuple under `JsonCodec`.

## After the type changes

An entry remembers the shape of its type: its classes, their fields and the fields' types. Say a
deploy adds a field or renames a class. The old entries then become misses, so a process never
decodes an entry into the wrong shape. During a rolling deploy, old and new processes each treat
the other's entries as misses and load. See [Core concepts](../../concepts.md#types) and
[Codecs](../codecs.md).
