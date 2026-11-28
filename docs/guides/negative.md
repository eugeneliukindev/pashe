# Negative caching

Someone asks for user 7, and there's no user 7. Without a cache, every request for user 7 asks the
source again, and gets the same answer. [`Negative`][pashe.options.Negative] caches that "not
found" instead. List the errors that mean "there's no such data" in
[`on`][pashe.options.Negative(on)], and pashe keeps each one for [`ttl`][pashe.options.Negative(ttl)].

=== "Sync"

    ```python hl_lines="21"
    --8<-- "staleness/not_found_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="21"
    --8<-- "staleness/not_found_async.py:show"
    ```

```mermaid
flowchart LR
    request(["get_user(7)"]) --> load{"the function"}
    load -- "a user" --> stored["stored for 300 s: MISS"]
    load -- "UserNotFoundError" --> missing["NotFoundError, remembered for 30 s: NOT_FOUND"]
    load -- "another error" --> raised["raised as it is"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class missing fromCache
    class load,stored fromSource
```

While a "not found" is kept, the cached function raises
[`NotFoundError`][pashe.errors.NotFoundError]. When the call has loaded right now, your function's
error is its cause. A stale result never hides a "not found".
