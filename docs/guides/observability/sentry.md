# Sentry

[`SentryHook`][pashe.contrib.sentry.SentryHook], from the `sentry` extra, leaves every error a
cache works around as a breadcrumb in Sentry.

=== "Sync"

    ```python hl_lines="6"
    --8<-- "observability/sentry_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6"
    --8<-- "observability/sentry_async.py:show"
    ```

Such an error, like a backend that's down, raises nothing: the call is still answered. So no
Sentry event would ever show it. As a breadcrumb, it shows up in the next event your app sends,
such as the request's error, with `pashe.operation` and `error.type`:

| Breadcrumb | Value |
| --- | --- |
| category | `pashe` |
| level | `warning` |
| message | `get: pashe.errors.BackendError` |
| data | `{"pashe.operation": "get", "error.type": "pashe.errors.BackendError"}` |

The call's key and the error's text are left out, since either one may name a user.

Turn on [`capture_errors`][pashe.contrib.sentry.SentryHook(capture_errors)], and it also sends
every such error as its own event. Leave it off unless you need it. While a backend is down,
every cached call would send one, and an [error metric](prometheus.md) shows the same thing for
free.
