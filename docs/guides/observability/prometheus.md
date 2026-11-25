# Prometheus

`PrometheusMetricsHook` of `pashe.contrib.prometheus`, the `prometheus` extra, records the
metrics of [OpenTelemetry](opentelemetry.md#metrics) through `prometheus_client`, named as its
Prometheus column says.

```python
--8<-- "observability/prometheus.py:show"
```

Make one hook per registry and give it to every cache, and to every near cache: a second hook over
the same registry raises `ValueError` of `prometheus_client`, as its metrics are there already.
`registry=` takes a registry of its own, as tests do; the global one by default. The histogram of
loads has the default buckets of `prometheus_client`.

---

API reference: [`pashe.contrib.prometheus`](../../reference/contrib/prometheus.md).
