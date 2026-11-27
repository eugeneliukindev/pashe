# Sentry

[`SentryHook`][pashe.contrib.sentry.SentryHook], the `sentry` extra, leaves every error a cache works
around as a breadcrumb in Sentry.

=== "Sync"

    ```python hl_lines="6"
    --8<-- "observability/sentry_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6"
    --8<-- "observability/sentry_async.py:show"
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

With [`capture_errors`][pashe.contrib.sentry.SentryHook(capture_errors)] on, it sends every such
error as an event of its own too. Leave it off unless you need it: while a backend is down every
cached call would send one, and a [metric of errors](prometheus.md) shows the same at no cost.
