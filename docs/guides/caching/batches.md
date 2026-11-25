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

Items the function leaves out are absent from the result and not stored. `batch` takes `ttl`,
`key`, `stampede` with its `jitter` and `max_concurrent_loads`, and `store`.

---

API reference: [`pashe`](../../reference/caches.md), [options](../../reference/options.md).
