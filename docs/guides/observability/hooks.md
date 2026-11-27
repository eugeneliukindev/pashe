# How hooks work

A cache tells its hooks how every call was answered and every error it worked around, for
metrics and logs. A hook subclasses [`Hook`][pashe.hooks.Hook] and overrides the methods it
needs; the others do nothing, so a hook keeps working when pashe tells of more. A cache calls its hooks in
the order of the list, in the task or thread of the call.

=== "Sync"

    ```python
    --8<-- "observability/hooks_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "observability/hooks_async.py:show"
    ```

A cache tells [`on_call`][pashe.hooks.Hook.on_call] of every call and
[`on_error`][pashe.hooks.Hook.on_error] of every error it works around. A rate limit tells
[`on_rate_limit`][pashe.hooks.Hook.on_rate_limit], a near cache
[`on_near_read`][pashe.hooks.Hook.on_near_read] and `on_near_flush`, and a circuit breaker
[`on_circuit`][pashe.hooks.Hook.on_circuit].

A field that takes a few values is a label for metrics, such as `label` of a
[`RateLimitDecision`][pashe.hooks.RateLimitDecision], `sources` of a
[`NearRead`][pashe.hooks.NearRead] and `state` of a [`Circuit`][pashe.hooks.Circuit]. The function
of an [`Outcome`][pashe.hooks.Outcome], such as `app.users.get_user`, is the same for every call of
it, a label too; the key is not, so keep it out of labels. The operation of a [`Failure`][pashe.hooks.Failure], such as
`get` or `publish`, tells what the cache was doing; its `error_type`, such as
`httpx.ConnectError` for a function that failed, is a label too.

A near cache is a backend, not a cache: it takes hooks of its own, for its reads and flushes.
Give it the hooks of the cache over it: see [The hooks of a near cache](#the-hooks-of-a-near-cache).

!!! warning "An error a hook raises goes up"

    A cache does not catch what its hooks raise: it is a bug of the hook, and fails the call it
    was raised in.

Ready hooks: [`LoggingHook`](logging.md) for the errors, [OpenTelemetry](opentelemetry.md) and
[`PrometheusMetricsHook`](prometheus.md) for metrics, and the `CacheHeadersHook` of the
[`CacheHeadersMiddleware`](../web/headers.md).

## The hooks of a near cache

A near cache answers some reads in memory and sends the rest to the shared backend; its hooks
tell how many went each way.

=== "Sync"

    ```python hl_lines="13 14 16"
    --8<-- "backends/near_cache_hooks_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="13 14 16"
    --8<-- "backends/near_cache_hooks_async.py:show"
    ```

Give [`hooks`][pashe.backends.NearCacheBackend(hooks)] the hooks of the cache, such as the
metrics of `pashe.contrib.opentelemetry`: a near cache with none tells nothing. It drops every copy
when it starts listening to its bus, and whenever messages of the bus may have been lost, and
tells [`on_near_flush`][pashe.hooks.Hook.on_near_flush] each time. A Redis bus takes
[`hooks`][pashe.contrib.redis.RedisPubSubBus(hooks)] too: it tells `on_error` of an error while it
listens other than a lost connection, such as of a hook, and listens again.
