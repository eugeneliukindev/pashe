# Values no function loads

[`@cache.value(...)`][pashe.Cache.value] keeps values that no function loads: what one place
writes and another reads later, such as a session, a one-time code or the result of a job. A miss
is `None`, not a load.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "caching_functions/value_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "caching_functions/value_async.py:show"
    ```

The function never runs, so its body raises `NotImplementedError`: mypy reports a body of `...` as
a function that returns nothing, and passes one that raises. It takes the [`ttl`][pashe.Cache.value(ttl)]
and [`key`][pashe.Cache.value(key)] of `@cache(...)`; the options about loads are not taken, as a
value has none.

A [`CachedValue`][pashe.CachedValue] raises [`BackendError`][pashe.errors.BackendError] when the
backend fails, where a cached function would load: with no load to answer with, "no value" and
"could not read it" must differ, as for a one-time code.

!!! tip "When there is a source, cache the function"

    A value is a place to keep what your code writes. When a miss can be loaded from a source,
    decorate the function that loads it with `@cache(...)`: it brings stale results, shared
    loads and the other answers to a source that is slow or down.
