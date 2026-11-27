# Storing only some results

By default, pashe stores every result. [`Store`][pashe.options.Store], from `pashe.options`, keeps
out the results that aren't worth keeping: one that [will change soon](#a-result-that-will-change),
or one the source [returns fast anyway](#a-load-that-was-fast).

## A result that will change

An order is final once it's done. Until then its status changes, so a cached order would show an
old status. [`when`][pashe.options.Store(when)] stores only the results it returns true for.

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

A result the source returns fast is cheap to reload, so you'd rather keep the room in the cache for
the slow ones. [`slower_than`][pashe.options.Store(slower_than)] stores only the results whose load
took at least that long.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "caching_functions/store_slower_than_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "caching_functions/store_slower_than_async.py:show"
    ```

## A result left out

The call still returns a result that's left out, and reports `MISS`. The rule holds however a
result gets in. If `when` refuses a result from `get_order.set(order, 1)` or `refresh`, the stored
one is dropped rather than kept. `set` loads nothing, so `slower_than` doesn't apply to it. In a
batch, `when` is checked for each item, and `slower_than` against the load of the whole batch.
