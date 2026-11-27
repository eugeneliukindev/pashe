# Negative caching

An error of the function that means "there is no such data" can be cached as the answer, so the source
is not asked again every time: [`Negative`][pashe.options.Negative] names those errors in
[`on`][pashe.options.Negative(on)] and keeps one for [`ttl`][pashe.options.Negative(ttl)].

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

The cached function raises [`NotFoundError`][pashe.errors.NotFoundError] then, with the error of
the function as its cause when it just loaded. A stale result never hides a "not found".
