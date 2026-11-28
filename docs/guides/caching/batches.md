# Batches

Some functions take many items and return a result for each: `f(items) -> {item: value}`.
[`@cache.batch(...)`][pashe.Cache.batch] caches every item on its own. A call reads all the items
in one backend call, then calls your function once with only the missing ones.

## Caching every item on its own

Say you cache a function that loads many users at once with plain `@cache(...)`. You get one entry
per list of users, so `[1, 2]` and `[2, 3]` don't share anything. A batch caches each item, so a
second list that has user 2 reads it from the cache.

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

The [`key`][pashe.Cache.batch(key)] is a template for one item, such as `"user:{}"`. A batch takes
the other options of `@cache(...)` too, except `negative`. Each option's page says how it works
with a batch.
