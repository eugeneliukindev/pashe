# Values no function loads

Some data has no function to load it. Your code writes it in one place and reads it later in
another: a session, a one-time code, the result of a background job. That's what
[`@cache.value(...)`][pashe.Cache.value] is for. When there's no entry, you get `None` back, and
nothing loads.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "caching_functions/value_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "caching_functions/value_async.py:show"
    ```

The decorated function never runs. Its parameters build the key, and its return annotation tells
pashe which type to decode. Why does the body raise `NotImplementedError` instead of `...`? Because
mypy reads `...` as a function that returns nothing, but it's fine with one that raises.

`@cache.value` takes the same [`ttl`][pashe.Cache.value(ttl)] and [`key`][pashe.Cache.value(key)]
as `@cache(...)`. The options about loads aren't there, since a value never loads.

## When the backend fails

A [`CachedValue`][pashe.CachedValue] raises [`BackendError`][pashe.errors.BackendError] when the
backend fails. A cached function would load from its source instead, but a value has no source to
fall back on. Think of a one-time code: "there's no code" and "we couldn't read the code" have to
look different to your code.

!!! tip "Got a source? Cache the function instead"

    A value is a place for data your code writes. If a miss can be loaded from somewhere, decorate
    the function that loads it with `@cache(...)`. You'll get stale results, shared loads and the
    other protections for a source that's slow or down.
