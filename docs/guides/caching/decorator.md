# Caching a function

[`@cache(...)`][pashe.Cache.__call__] caches the results of a function, `def` for a `Cache` and
`async def` for an `AsyncCache`: the first call of the arguments runs it and stores the result,
the next ones are answered from the backend until its TTL ends.

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_async.py:show"
    ```

Every other option of `@cache(...)` has a page of its own: [Every option](#every-option) lists
them.

!!! warning "Do not change a result in place"

    Concurrent calls of a key that miss together share one load, and get the same object: a change
    one caller makes, another sees. Copy a result before you change it. See
    [Sharing a load within a process](../stampedes.md#sharing-a-load-within-a-process).

## Reading and writing a result

=== "Sync"

    ```python
    --8<-- "caching_functions/methods_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/methods_async.py:show"
    ```

The methods of a [`CachedFunction`][pashe.CachedFunction] take the same arguments as the
function, so they find the same entry.

!!! warning "Cached methods share one entry across instances"

    A method can be cached too. `self` and `cls` are left out of the default key, so every
    instance shares one entry per arguments; when the result depends on the instance, name it in
    the template, such as `key="user:{self.id}"`.

## Every option

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_options_async.py:show"
    ```

Each option has a page of its own: [`ttl`](ttl.md), [`key`](keys.md), [`tags`](../tags.md),
[`stale`](../stale.md), [`stampede`](../stampedes.md), [`negative`](../negative.md) and
[`store`](../store.md).
