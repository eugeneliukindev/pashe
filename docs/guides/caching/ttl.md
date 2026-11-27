# TTL: how long a result is kept

How long a result stays fresh, with [`ttl`][pashe.Cache.__call__(ttl)]: seconds, a `timedelta`,
or a function of the result.

## How long a result is fresh

A result is fresh for `ttl`: the calls in that time get it from the cache. The first call after it
loads it anew and stores the new result.

=== "Sync"

    ```python hl_lines="13"
    --8<-- "caching_functions/ttl_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="13"
    --8<-- "caching_functions/ttl_async.py:show"
    ```

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 60" data-start="0"><b>HIT</b><br>fresh, from the cache</div>
<div class="pashe-timeline__source" data-start="60 s"><b>MISS</b><br>the next call loads and stores anew</div>
</div>

## TTL from the result

When the result says how long it is valid, as a token does, give `ttl` a function of it:

=== "Sync"

    ```python hl_lines="14"
    --8<-- "caching_functions/ttl_from_result_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "caching_functions/ttl_from_result_async.py:show"
    ```

!!! warning "A negative TTL is an error, not a way to skip a result"

    A result the function gives a negative TTL is not stored, and the error goes to `on_error`.
    To leave a result out on purpose use [`Store(when=...)`](../store.md#a-result-that-will-change).
