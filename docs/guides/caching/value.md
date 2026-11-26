# Values no function loads

`@cache.value(...)` keeps values that no function loads: what one place writes and another reads
later, such as a session, a one-time code or the result of a job. It takes the `ttl`, `key` and
`tags` of `@cache(...)`; a miss is `None`, not a load. It makes a `CachedValue`, an
`AsyncCachedValue` on the async side.

=== "Sync"

    ```python
    --8<-- "caching_functions/value_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/value_async.py:show"
    ```

The function never runs: its parameters fill the templates of the key and the tags, and its return
annotation says what a value decodes as. Its body raises `NotImplementedError`: mypy reports a body
of `...` as a function that returns nothing, and passes one that raises.

| | `@cache` | `@cache.value` |
| --- | --- | --- |
| `f(...)` | the result, loaded on a miss | - |
| `.get(...)` | the fresh result or `None`, loading nothing | the fresh value or `None` |
| `.set(value, ...)` | stores the result | stores the value |
| `.invalidate(...)` | drops it | drops it |
| `.refresh(...)` | loads it again | - |

A value is stored as a cached result is: the prefix, the codec, the compressor, the hooks and
`invalidate_tags` work the same. `stale`, `stampede`, `negative` and `store` are not taken: they
are about loads, and a value has none. A backend that fails raises `BackendError` from `get`,
`set` and `invalidate`: with no load to answer with, "no value" and "could not read it" must
differ, as for a one-time code.

!!! tip "When there is a source, cache the function"

    A value is a place to keep what your code writes. When a miss can be loaded from a source,
    decorate the function that loads it with `@cache(...)`: it brings stale results, single
    flight and the other answers to a source that is slow or down.

---

API reference: [`Cache.value`](../../reference/caches.md#pashe.Cache.value), [`CachedValue`](../../reference/caches.md#pashe.CachedValue).
