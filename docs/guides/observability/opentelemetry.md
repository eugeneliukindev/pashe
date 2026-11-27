# OpenTelemetry

[`pashe.contrib.opentelemetry`][pashe.contrib.opentelemetry], from the `opentelemetry` extra, has
two hooks. [`OtelMetricsHook`][pashe.contrib.opentelemetry.OtelMetricsHook] records metrics.
[`OtelSpanEventsHook`][pashe.contrib.opentelemetry.OtelSpanEventsHook] adds every cached call to
the current span.

=== "Sync"

    ```python hl_lines="6 7"
    --8<-- "observability/opentelemetry_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6 7"
    --8<-- "observability/opentelemetry_async.py:show"
    ```

The extra installs only the API, as OpenTelemetry asks libraries to do. Your app sets up the SDK
and its exporters. Without them, the hooks record nothing and cost next to nothing.

## Metrics

OpenTelemetry has no semantic convention for caches yet, so the names follow its general rules
under the `pashe` namespace. OpenTelemetry's Prometheus exporter turns them into the names in the
Prometheus column. [`PrometheusMetricsHook`](prometheus.md) writes the same names, so one
dashboard works with either.

| OpenTelemetry | Prometheus | What it counts | By |
| --- | --- | --- | --- |
| `pashe.calls`, `{call}` | `pashe_calls_total` | every cached call and item of a batch | function, status |
| `pashe.load.duration`, `s` | `pashe_load_duration_seconds` | every run of a function for a call | function |
| `pashe.errors`, `{error}` | `pashe_errors_total` | every error a cache works around | operation, `error.type` |
| `pashe.rate_limit.calls`, `{call}` | `pashe_rate_limit_calls_total` | every call a rate limit counted | result: `allowed`, `refused` |
| `pashe.near.reads`, `{read}` | `pashe_near_reads_total` | every key a near cache read, given the hook | source: `local`, `shared` |
| `pashe.near.flushes`, `{flush}` | `pashe_near_flushes_total` | every time such a near cache dropped every copy | |
| `pashe.circuit.changes`, `{change}` | `pashe_circuit_changes_total` | every time a `CircuitBreaker` given the hook opened or closed | state: `open`, `closed` |

A call's key is never a label, because each key would create its own series. The same goes for a
rate limit's key, so rate limit calls count by result only.

## Span events

`OtelSpanEventsHook` adds every cached call to the current span as a `pashe.call` event. The
event holds the function, the key, the status, and how long the result stays fresh, as
`pashe.fresh_seconds`. Every error the cache worked around becomes an exception event. So a trace
shows which calls in a request the cache answered. The span keeps its status, since the cache did
answer.

!!! warning "The events hold the key"

    If a key template holds personal data, use a digest, such as `{email:hmac}`. The trace goes
    to whatever service stores your traces.
