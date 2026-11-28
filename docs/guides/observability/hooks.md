# How hooks work

Want metrics or logs? A cache tells its hooks how it answered each call, and about each error it
worked around. To write a hook, subclass [`Hook`][pashe.hooks.Hook] and override the methods you
need. The others do nothing, so your hook keeps working when pashe adds new events. A cache calls
its hooks in list order, in the same task or thread as the call.

=== "Sync"

    ```python
    --8<-- "observability/hooks_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "observability/hooks_async.py:show"
    ```

A cache calls [`on_call`][pashe.hooks.Hook.on_call] for every call and
[`on_error`][pashe.hooks.Hook.on_error] for every error it works around. A rate limit calls
[`on_rate_limit`][pashe.hooks.Hook.on_rate_limit]. A near cache calls
[`on_near_read`][pashe.hooks.Hook.on_near_read] and `on_near_flush`. A circuit breaker calls
[`on_circuit`][pashe.hooks.Hook.on_circuit].

Which fields make good metric labels? The ones with only a few values: a
[`RateLimitDecision`][pashe.hooks.RateLimitDecision]'s `label`, a
[`NearRead`][pashe.hooks.NearRead]'s `sources` and a [`Circuit`][pashe.hooks.Circuit]'s `state`.
An [`Outcome`][pashe.hooks.Outcome]'s function, such as `app.users.get_user`, is the same for
every call to it, so it's a label too. The key isn't: keep it out of labels. A
[`Failure`][pashe.hooks.Failure]'s operation, such as `get` or `publish`, says what the cache was
doing. Its `error_type`, such as `httpx.ConnectError` for a function that failed, is a label too.

A near cache is a backend, not a cache, so it takes its own hooks for its reads and flushes. Give
it the same hooks as the cache on top of it: see
[The hooks of a near cache](#the-hooks-of-a-near-cache).

!!! warning "An error a hook raises goes up"

    A cache doesn't catch what its hooks raise. Such an error is a bug in the hook, and it fails
    the call it was raised in.

pashe comes with ready hooks: [`LoggingHook`](logging.md) for errors,
[OpenTelemetry](opentelemetry.md) and [`PrometheusMetricsHook`](prometheus.md) for metrics, and the
`CacheHeadersHook` of [`CacheHeadersMiddleware`](../web/headers.md).

## The hooks of a near cache

A near cache answers some reads from memory and sends the rest to the shared backend. Its hooks
tell you how many went each way.

=== "Sync"

    ```python hl_lines="13 14 16"
    --8<-- "backends/near_cache_hooks_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="13 14 16"
    --8<-- "backends/near_cache_hooks_async.py:show"
    ```

Pass the cache's hooks to [`hooks`][pashe.backends.NearCacheBackend(hooks)], such as the metrics
from `pashe.contrib.opentelemetry`. A near cache with no hooks tells you nothing.

A near cache drops every copy when it starts listening to its bus, and again whenever bus messages
may have been lost. Each time, it calls [`on_near_flush`][pashe.hooks.Hook.on_near_flush].

A Redis bus takes [`hooks`][pashe.contrib.redis.RedisPubSubBus(hooks)] too. If an error other than
a lost connection happens while it listens, such as one from a hook, the bus calls `on_error` and
starts listening again.
