# Types

A cached function is typed as the function it caches: a type checker sees the same parameters
and the same result, and a stored result comes back as that result, not as the `dict` it was
encoded into.

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

The return annotation of the function says what a stored result decodes as; for a batch, the
type of the values of the `dict` it returns. The codec does the work, so the codec decides which
types come back whole: [Codecs](../values/codecs.md) tells which.

A type the codec would give back as another one is refused when the function is decorated, not
when its first result is read: a dataclass under `JsonCodec` raises `InvalidOptionsError`, which
names the codecs that rebuild it. A function without a return annotation gets back what the
codec reads on its own.

## After the type changes

An entry remembers the shape of its type: its classes, their fields and the types of those. A
deploy that adds a field or renames a class makes the old entries misses, so a process never
decodes an entry into the wrong form; during a rolling deploy the old and the new processes each
take the entries of the other for misses and load. See [Core concepts](../../concepts.md#types) and [Codecs](../values/codecs.md).

---

API reference: [`pashe`](../../reference/caches.md), [`pashe.codecs`](../../reference/codecs.md).
