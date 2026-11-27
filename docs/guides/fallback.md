# A failing backend

A cache reads and writes through its backend; when Redis fails, cached functions still answer:
they load from the source, and the error goes to `on_error`. A
[`Fallback`][pashe.options.Fallback] keeps those results so the source gets one load per key and
process instead of one per call:

=== "Sync"

    ```python
    --8<-- "staleness/fallback_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "staleness/fallback_async.py"
    ```

```mermaid
flowchart LR
    subgraph p1["Process 1"]
        request(["a call"])
        fallback["fallback: the memory of the process, 30 s"]
    end
    subgraph shared["Redis: every process"]
        redis[("entries")]
    end
    source["the function"]
    request -- "Redis answers" --> redis
    request -. "Redis is down" .-> fallback
    fallback -- "miss" --> source
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class redis,fallback fromCache
    class source fromSource
    style p1 fill:#2b5b8424,stroke:#2b5b84
    style p2 fill:#00968824,stroke:#009688
    style shared fill:#f7b5002e,stroke:#c98f00
```

!!! warning "No invalidation reaches the fallback"

    While Redis is down, `invalidate_tags` and `invalidate` cannot reach the fallback, so a
    result stays there for at most [`Fallback.ttl`][pashe.options.Fallback(ttl)], 30 seconds by
    default: a longer one spares the source more, a shorter one answers with older results for
    less time.

## Skip a backend that is down

Until Redis answers again, every call waits for the timeout of its connection before it loads.
Two settings bound that wait: short timeouts of the client, and a
[`CircuitBreaker`][pashe.backends.CircuitBreaker] of `pashe.backends`, which skips Redis for a
while once it failed several times in a row:

=== "Sync"

    ```python hl_lines="10 11 13 14"
    --8<-- "backends/breaker_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="10 11 13 14"
    --8<-- "backends/breaker_async.py:show"
    ```

| Calls | What happens |
| --- | --- |
| the first 5 while Redis is down | each waits the timeout of the client, then answers from the fallback or the source |
| the next ones, for 10 s | each skips Redis at once: [`CircuitOpenError`][pashe.errors.CircuitOpenError], a `BackendError`, goes to `on_error` |
| after 10 s | one call tries Redis: an answer closes the breaker, a failure opens it for 10 s more |

Give the same breaker to the bus of a near cache over the same
Redis, `RedisPubSubBus(client, breaker=breaker)`, so both skip it together. A hook hears when it
opens and closes through `on_circuit`: an alert of a Redis that is down.

A backend takes any [`Breaker`][pashe.backends.Breaker] of `pashe.backends`: another policy
subclasses it.
