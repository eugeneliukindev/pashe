# Logging

A cache answers from the function when its backend fails, and raises nothing. Give it a
[`LoggingHook`][pashe.hooks.LoggingHook], or an `on_error` of your own, or no one sees a backend that is
down.

=== "Sync"

    ```python hl_lines="7 8"
    --8<-- "observability/logging_hook_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7 8"
    --8<-- "observability/logging_hook_async.py:show"
    ```

It logs every error a cache works around as a warning, with the traceback, to the logger `pashe` or
the [`logger`][pashe.hooks.LoggingHook(logger)] it is given. A record has the extra fields
`pashe_operation` and `pashe_key`, for structured logs. pashe logs nothing without the hook.

!!! note "One warning per call while a backend is down"

    Every cached call meets the backend that is down, so every call logs one. Filter or rate
    them in the logging of the application, or count them with the metrics instead.
