# OpenTelemetry

`pashe.contrib.opentelemetry`, the `opentelemetry` extra, has two hooks: `OtelMetricsHook`
records metrics, and `OtelSpanEventsHook` adds every cached call to the current span.

```python
--8<-- "observability/opentelemetry.py:show"
```

The extra brings the API only, as OpenTelemetry asks of a library: the application sets up the
SDK and its exporters, and without them the hooks record nothing and cost next to nothing.

## Metrics

No semantic convention of OpenTelemetry covers caches yet, so the names follow its general rules
under the `pashe` namespace. The Prometheus exporter of OpenTelemetry turns them into the names of
the Prometheus column, which [`PrometheusMetricsHook`](prometheus.md) writes too, so one dashboard reads either.

| OpenTelemetry | Prometheus | What it counts | By |
| --- | --- | --- | --- |
| `pashe.calls`, `{call}` | `pashe_calls_total` | every cached call and item of a batch | function, status |
| `pashe.load.duration`, `s` | `pashe_load_duration_seconds` | every run of a function for a call | function |
| `pashe.errors`, `{error}` | `pashe_errors_total` | every error a cache works around | operation, `error.type` |
| `pashe.rate_limit.calls`, `{call}` | `pashe_rate_limit_calls_total` | every call a rate limit counted | result: `allowed`, `refused` |
| `pashe.near.reads`, `{read}` | `pashe_near_reads_total` | every key a near cache read, given the hook | source: `local`, `shared` |
| `pashe.near.flushes`, `{flush}` | `pashe_near_flushes_total` | every time such a near cache dropped every copy | |
| `pashe.circuit.changes`, `{change}` | `pashe_circuit_changes_total` | every time a `CircuitBreaker` given the hook opened or closed | state: `open`, `closed` |

The key of a call is never a label, as each key would make series of its own; the key of a rate
limit neither, so its calls count by result only.

API reference: [`OtelMetricsHook`](../../reference/contrib/opentelemetry.md#pashe.contrib.opentelemetry.OtelMetricsHook).

## Span events

`OtelSpanEventsHook` adds every cached call to the current span as the event `pashe.call`, with
the function, the key, the status and how long the result stays fresh, `pashe.fresh_seconds`, and every
error worked around as an exception
event, so a trace tells which calls of a request the cache answered. The span keeps its status,
as the cache answered.

!!! warning "The events hold the key"

    Give the templates of keys that hold personal data a digest, such as `{email:hmac}`: the
    trace goes to the service that keeps it.

---

API reference: [`pashe.contrib.opentelemetry`](../../reference/contrib/opentelemetry.md).
