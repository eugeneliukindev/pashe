# Reusing options

A group of options is a frozen object: a policy shared by many functions is one value. For
several groups at once, a `functools.partial` keeps every argument checked by type checkers:

=== "Sync"

    ```python
    --8<-- "caching_functions/reusing_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/reusing_async.py:show"
    ```

---

API reference: [`pashe`](../../reference/caches.md), [options](../../reference/options.md).
