# Prometheus

[`PrometheusMetricsHook`][pashe.contrib.prometheus.PrometheusMetricsHook], the `prometheus` extra, records the
metrics of [OpenTelemetry](opentelemetry.md#metrics) through `prometheus_client`, named as its
Prometheus column says.

=== "Sync"

    ```python hl_lines="6 7"
    --8<-- "observability/prometheus_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6 7"
    --8<-- "observability/prometheus_async.py:show"
    ```

Make one hook per registry and give it to every cache, and to every near cache: a second hook over
the same registry raises `ValueError` of `prometheus_client`, as its metrics are there already.
[`registry`][pashe.contrib.prometheus.PrometheusMetricsHook(registry)] takes a registry of its
own, as tests do. The histogram of
loads has the default buckets of `prometheus_client`.
