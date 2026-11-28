# Caching a function

[`@cache(...)`][pashe.Cache.__call__] caches what your function returns. Use `def` functions with a
`Cache` and `async def` ones with an `AsyncCache`. The first call with some arguments runs the
function and stores its result. Later calls with the same arguments get it from the backend, until
its TTL ends.

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_async.py:show"
    ```

That's the core of pashe. Every other option of `@cache(...)` has its own page, and
[Every option](#every-option) lists them all.

!!! warning "Don't change a result in place"

    When several calls miss the same key at once, they share one load and get the same object.
    So if one caller changes it, the others see the change. Copy a result before you change it.
    See [Sharing a load within a process](../stampedes.md#sharing-a-load-within-a-process).

## Reading and writing a result

=== "Sync"

    ```python
    --8<-- "caching_functions/methods_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/methods_async.py:show"
    ```

The methods of a [`CachedFunction`][pashe.CachedFunction] take the same arguments as your
function, so they find the same entry.

!!! warning "Cached methods share one entry across instances"

    You can cache a method too. The default key leaves out `self` and `cls`, so all instances
    share one entry for the same arguments. If the result depends on the instance, put it in the
    template, such as `key="user:{self.id}"`.

## Every option

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_options_async.py:show"
    ```

Each option has its own page: [`ttl`](ttl.md), [`key`](keys.md), [`tags`](../tags.md),
[`stale`](../stale.md), [`stampede`](../stampedes.md), [`negative`](../negative.md) and
[`store`](../store.md).
