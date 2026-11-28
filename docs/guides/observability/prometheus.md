# Prometheus

[`PrometheusMetricsHook`][pashe.contrib.prometheus.PrometheusMetricsHook], from the `prometheus`
extra, records the same metrics as [OpenTelemetry](opentelemetry.md#metrics) through
`prometheus_client`, with the names from the Prometheus column.

=== "Sync"

    ```python hl_lines="6 7"
    --8<-- "observability/prometheus_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6 7"
    --8<-- "observability/prometheus_async.py:show"
    ```

Make one hook per registry and give it to every cache and every near cache. A second hook on the
same registry raises a `prometheus_client` `ValueError`, because its metrics are there already.
To use a separate registry, as tests do, pass it to
[`registry`][pashe.contrib.prometheus.PrometheusMetricsHook(registry)]. The load histogram uses
the default `prometheus_client` buckets.
