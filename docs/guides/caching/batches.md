# Batches

A function of many items, `f(items) -> {item: value}`, caches every item on its own: a call reads
all items in one backend call and calls the function once with the missing ones.

=== "Sync"

    ```python
    --8<-- "caching_functions/batches_sync.py:show"
    --8<-- "caching_functions/batches_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/batches_async.py:show"
    --8<-- "caching_functions/batches_async.py:calls"
    ```

`@cache.batch(...)` makes a `CachedBatchFunction`, an `AsyncCachedBatchFunction` on the async side.
Items the function leaves out are absent from the result and not stored. `batch` takes `ttl`,
`key`, `stampede` with its `jitter` and `max_loads`, and `store`.

---

API reference: [`Cache.batch`](../../reference/caches.md#pashe.Cache.batch), [`CachedBatchFunction`](../../reference/caches.md#pashe.CachedBatchFunction).
