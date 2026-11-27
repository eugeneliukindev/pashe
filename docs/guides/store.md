# Storing only some results

By default every result is stored. [`Store`][pashe.options.Store], from `pashe.options`, keeps out
the results not worth keeping: one that [will change soon](#a-result-that-will-change), or one the
source [gives fast anyway](#a-load-that-was-fast).

## A result that will change

An order is final once it is done; until then its status changes, so caching it would answer
with an old status. [`when`][pashe.options.Store(when)] stores only the results it returns true
for.

=== "Sync"

    ```python hl_lines="10"
    --8<-- "caching_functions/store_when_sync.py:show"
    --8<-- "caching_functions/store_when_sync.py:calls"
    ```

=== "Async"

    ```python hl_lines="10"
    --8<-- "caching_functions/store_when_async.py:show"
    --8<-- "caching_functions/store_when_async.py:calls"
    ```

## A load that was fast

A result the source gives fast is cheap to reload, so the room in the cache goes to the slow
ones: [`slower_than`][pashe.options.Store(slower_than)] stores only the results whose load took
at least that long.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "caching_functions/store_slower_than_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "caching_functions/store_slower_than_async.py:show"
    ```

## A result left out

A result left out is still answered, and the call reports `MISS`. The rule holds for every way a
result gets in: `get_order.set(order, 1)` and `refresh` with a result `when` refuses drop the
stored one instead of keeping it. `set` loads nothing, so `slower_than` does not apply to it. In
a batch `when` is checked per item, and `slower_than` against the load of the whole batch.
