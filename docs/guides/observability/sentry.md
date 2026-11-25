# Sentry

`SentryHook` of `pashe.contrib.sentry`, the `sentry` extra, leaves every error a cache works
around as a breadcrumb in Sentry.

```python
--8<-- "observability/sentry.py:show"
```

Such an error, as a backend that is down, raises nothing: the call is answered all the same, so
no event of Sentry would show it. As a breadcrumb it shows in the next event the application
sends, such as the error of the request, with `pashe.operation` and `error.type`:

| Breadcrumb | Value |
| --- | --- |
| category | `pashe` |
| level | `warning` |
| message | `get: pashe.errors.BackendError` |
| data | `{"pashe.operation": "get", "error.type": "pashe.errors.BackendError"}` |

The key of the call and the text of the error are left out: either may name a user.

`SentryHook(capture_errors=True)` sends every such error as an event of its own too, with the tag
`pashe.operation` and the text of the error. It is off by default: while a backend is down every
cached call would send one; a [metric of errors](prometheus.md) shows the same at no cost.

---

API reference: [`pashe.contrib.sentry`](../../reference/contrib/sentry.md).
