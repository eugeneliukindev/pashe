# Batches

A function of many items, `f(items) -> {item: value}`, caches every item on its own with
[`@cache.batch(...)`][pashe.Cache.batch]: a call reads all items in one backend call and calls the
function once with the missing ones.

## Caching every item on its own

A function that loads many items at once would cache them as one entry per list of items; a
batch caches each item, so another list that shares it reads it from the cache.

=== "Sync"

    ```python hl_lines="17"
    --8<-- "caching_functions/batches_sync.py:show"
    --8<-- "caching_functions/batches_sync.py:calls"
    ```

=== "Async"

    ```python hl_lines="17"
    --8<-- "caching_functions/batches_async.py:show"
    --8<-- "caching_functions/batches_async.py:calls"
    ```

Its [`key`][pashe.Cache.batch(key)] is a template over the item, such as `"user:{}"`. It takes
the other options of `@cache(...)` too, but `negative`: the page of each tells how it works with a
batch.
