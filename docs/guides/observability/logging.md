# Logging

When its backend fails, a cache calls the function and raises nothing. That's good for your
users, but it means nobody notices a backend that's down. Give the cache a
[`LoggingHook`][pashe.hooks.LoggingHook], or your own `on_error`.

=== "Sync"

    ```python hl_lines="7 8"
    --8<-- "observability/logging_hook_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7 8"
    --8<-- "observability/logging_hook_async.py:show"
    ```

It logs every error the cache works around as a warning, with the traceback. It writes to the
`pashe` logger, or to the [`logger`][pashe.hooks.LoggingHook(logger)] you pass. Each record has the
extra fields `pashe_operation` and `pashe_key`, for structured logs. Without the hook, pashe logs
nothing.

!!! note "One warning per call while a backend is down"

    Every cached call hits the backend that's down, so every call logs a warning. Filter or
    rate-limit them in your app's logging, or count them with metrics instead.
