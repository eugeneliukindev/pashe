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
Items the function leaves out are absent from the result and not stored. `batch` takes the
options of `@cache(...)` but `negative`: `ttl`; `key` and `tags`, templates over the item, so
`invalidate_tags("user:3")` makes item 3 a miss in the batch and in `get_user(3)` alike; `stale`
with its `if_error`; `stampede` with its `jitter` and `max_loads`; and `store`.

When the function raises, the stale results of the items answer, if each item it loads has one
within `if_error`, and the error goes to `on_error`; with one item short of a stale result, the
call raises, as the items are one call. A batch waits for its load and loads nothing in the
background, so it refuses `while_revalidate`, `if_slow`, `lock_for` and `revalidate_before`.

---

API reference: [`Cache.batch`](../../reference/caches.md#pashe.Cache.batch), [`CachedBatchFunction`](../../reference/caches.md#pashe.CachedBatchFunction).
