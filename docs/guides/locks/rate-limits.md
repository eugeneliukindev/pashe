# Rate limits

`RateLimiter` of `pashe`, `AsyncRateLimiter` on the async side, counts calls for a key in a
backend, so every process over it shares the count, and refuses those over the limit with
`RateLimitedError`: `limiter.count` counts one call, `@limiter.limited` every call of a function.
The counters live apart from the entries of a cache over the same backend and `prefix`, and the
limiter closes nothing: the backend belongs to whoever made it.

!!! info "Where it works"

    In the backend: every process of every machine over Redis, every process of one machine over
    SQLite, one process over memory. See [Where each feature works](../choosing.md#where-each-feature-works).

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_async.py:show"
    ```

=== "SlidingWindow"

    === "Sync"

        ```python
        --8<-- "locks_and_rate_limits/sliding_window_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "locks_and_rate_limits/sliding_window_async.py:show"
        ```

    About `calls` calls pass in any span of `per` seconds, even across the edge of two windows;
    refused calls are not counted. `SlidingWindow.per_second(n)`, `per_minute(n)` and `per_hour(n)` make one; `FixedWindow` has the same, with `ban_for=`.

=== "FixedWindow"

    === "Sync"

        ```python
        --8<-- "locks_and_rate_limits/fixed_window_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "locks_and_rate_limits/fixed_window_async.py:show"
        ```

    `calls` pass per window that starts with the first call; the first call over it blocks the
    key for `ban_for`, or for `per` without it:

    ```mermaid
    flowchart LR
        window["0 to 60 s<br/>calls 1 to 5 pass"] -- "call 6" --> ban["the next 300 s<br/>every call raises RateLimitedError"]
        ban --> next["after the ban<br/>the next call starts a new window"]
        window -. "60 s pass" .-> next
        classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
        classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
        class window,next fromCache
        class ban fromSource
    ```

`RateLimitedError.retry_after` says how long to wait, for a `Retry-After` header. `cost` counts a
heavy call as several. A failing backend lets the call through uncounted and reports to `on_error`.

Each limit keeps counters of its own, named by the key and the limit. Two limits on one key, such
as 10 calls a minute and 100 an hour for one address, count apart, and a call passes when every
one of them lets it. One limit used in two places on one key shares its counters.

API reference: [`RateLimiter`](../../reference/caches.md#pashe.RateLimiter),
[`RateLimiter.count`](../../reference/caches.md#pashe.RateLimiter.count),
[`RateLimiter.limited`](../../reference/caches.md#pashe.RateLimiter.limited),
[`SlidingWindow`](../../reference/ratelimit.md#pashe.ratelimit.SlidingWindow),
[`FixedWindow`](../../reference/ratelimit.md#pashe.ratelimit.FixedWindow),
[`RateLimitState`](../../reference/ratelimit.md#pashe.ratelimit.RateLimitState),
[`RateLimitedError`](../../reference/errors.md#pashe.errors.RateLimitedError).

## Every option

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_options_async.py:show"
    ```

`count` returns a `RateLimitState` of `pashe.ratelimit`: the calls of the limit, those left,
and the seconds until the window resets.

!!! warning "A limit is checked in a few calls to the backend, not at once"

    A sliding window adds the call to its counter, reads the last window, and takes the call back
    if it is over the limit; a fixed window adds the call, then reads or sets the time left. In
    between, other processes see the call counted: under a burst right at the limit, a few calls
    may be refused that a single check would let through. Calls over the limit are never let
    through.

!!! tip "Fail closed where a limit guards against abuse"

    For limits of logins or of password resets, pass `fail_open=False`: a failing backend then
    raises `BackendError` instead of letting every call through.

---

API reference: [`pashe.ratelimit`](../../reference/ratelimit.md).
