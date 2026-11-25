# How hooks work

A cache tells its hooks how every call was answered and every error it worked around, for
metrics and logs. A hook subclasses `Hook` of `pashe.hooks` and overrides the methods it needs; the
others do nothing, so a hook keeps working when pashe tells of more. A cache calls its hooks in
the order of the list, in the task or thread of the call.

=== "Sync"

    ```python
    --8<-- "observability/hooks_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "observability/hooks_async.py:show"
    ```

| Method | Gets | When |
| --- | --- | --- |
| `on_call` | an `Outcome`: the function, the key, the `CacheStatus`, the seconds of the load, how long the result stays fresh | every cached call, and every item of a batch |
| `on_error` | a `Failure`: the `Operation`, the key and the error, as the backend or the loader raised it | every error the cache works around instead of raising it |
| `on_rate_limit` | a `RateLimitDecision`: the key, and whether the call went through | every call a rate limit counted |
| `on_near_read` | a `NearRead`: the keys its copies answered, and those read from the shared backend | every read of a near cache given the hook |
| `on_near_flush` | nothing | a near cache given the hook dropped every copy |
| `on_circuit` | a `Circuit`: whether it opened or closed, and the failures in a row that opened it | the `CircuitBreaker` of a backend, given the hook, opened or closed |

The function of an `Outcome`, such as `app.users.get_user`, is the same for every call of it, a
label for metrics; the key is not, so keep it out of labels. The operation of a `Failure`, such as
`get` or `publish`, tells what the cache was doing; its `error_type`, such as
`httpx.ConnectError` for a loader that failed, is a label too.

A near cache is a backend, not a cache: it takes `hooks=` of its own, for its reads and flushes.
Give it the hooks of the cache over it.

!!! warning "An error a hook raises goes up"

    A cache does not catch what its hooks raise: it is a bug of the hook, and fails the call it
    was raised in.

Ready hooks: [`LoggingHook`](logging.md) for the errors, [OpenTelemetry](opentelemetry.md) and
[`PrometheusMetricsHook`](prometheus.md) for metrics, and the `CacheHeadersHook` of the
[`CacheHeadersMiddleware`](../web/headers.md).

---

API reference: [`pashe.hooks`](../../reference/hooks.md).
