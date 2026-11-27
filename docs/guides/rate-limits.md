# Rate limits

[`RateLimiter`][pashe.RateLimiter] of `pashe`, [`AsyncRateLimiter`][pashe.AsyncRateLimiter] on the
async side, counts calls for a key in a backend, so every process over it shares the count, and
refuses those over the limit with [`RateLimitedError`][pashe.errors.RateLimitedError]. A limit is
a [sliding window](#a-sliding-window) or a [fixed window with a ban](#a-fixed-window-and-a-ban); a
call can [weigh more](#a-heavy-call), a [failing backend](#when-the-backend-fails) lets calls
through, and [HTTP requests](#rate-limits-of-http-requests) are limited by a middleware or a
dependency of FastAPI. The counters live apart from the entries of a cache over the same backend
and `prefix`, and the limiter closes nothing: the backend belongs to whoever made it.

!!! info "Where it works"

    In the backend: every process of every machine over Redis, every process of one machine over
    SQLite, one process over memory. See [Where each feature works](choosing.md#where-each-feature-works).

## Counting a call and limiting a function

[`limiter.count`][pashe.RateLimiter.count] counts one call of a key, where you choose the key,
such as the address of a client; [`@limiter.limited`][pashe.RateLimiter.limited] counts every call
of a function, by a [`key`][pashe.RateLimiter.limited(key)] template over its arguments, as of
`@cache`, or by one counter for the function without one.

=== "Sync"

    ```python hl_lines="16 22"
    --8<-- "locks_and_rate_limits/rate_limit_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="16 22"
    --8<-- "locks_and_rate_limits/rate_limit_async.py:show"
    ```

A call over the limit raises `RateLimitedError`, whose `retry_after` feeds a `Retry-After`
header. `count` returns a [`RateLimitState`][pashe.ratelimit.RateLimitState]: what is left of the
limit.

Each limit keeps counters of its own, named by the key and the limit. Two limits on one key, such
as 10 calls a minute and 100 an hour for one address, count apart, and a call passes when every
one of them lets it. One limit used in two places on one key shares its counters.

!!! warning "A limit is checked in a few calls to the backend, not at once"

    A sliding window adds the call to its counter, reads the last window, and takes the call back
    if it is over the limit; a fixed window adds the call, then reads or sets the time left. In
    between, other processes see the call counted: under a burst right at the limit, a few calls
    may be refused that a single check would let through. Calls over the limit are never let
    through.

## A sliding window

With [`SlidingWindow`][pashe.ratelimit.SlidingWindow], about `calls` calls pass in any span of
`per` seconds, even across the edge of two windows.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "locks_and_rate_limits/sliding_window_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "locks_and_rate_limits/sliding_window_async.py:show"
    ```

Refused calls are not counted, so a client that keeps calling over the limit gets through again
as soon as the span has room.

## A fixed window and a ban

With [`FixedWindow`][pashe.ratelimit.FixedWindow], `calls` pass per window that starts with the
first call; the first call over it blocks the key for `ban_for`, as long as the window when it is
not given.

=== "Sync"

    ```python hl_lines="7"
    --8<-- "locks_and_rate_limits/fixed_window_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7"
    --8<-- "locks_and_rate_limits/fixed_window_async.py:show"
    ```

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 20" data-start="0"><b>calls 1 to 5</b><br>pass</div>
<div class="pashe-timeline__source" style="flex: 300" data-start="20 s"><b>call 6 bans the key</b><br>every call raises RateLimitedError</div>
<div class="pashe-timeline__fresh" data-start="320 s"><b>the next call</b><br>starts a new window</div>
</div>

## A heavy call

A call that costs the source more than the others, such as an exact search, counts as several:
its [`cost`][pashe.RateLimiter.count(cost)].

=== "Sync"

    ```python hl_lines="10"
    --8<-- "locks_and_rate_limits/cost_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="10"
    --8<-- "locks_and_rate_limits/cost_async.py:show"
    ```

## When the backend fails

A failing backend lets the call through uncounted and reports to `on_error`: a rate limit that
fails takes no service down. Where a limit guards against abuse, as of logins or of password
resets, fail closed instead: with [`fail_open`][pashe.RateLimiter.count(fail_open)] off a failing
backend raises [`BackendError`][pashe.errors.BackendError].

=== "Sync"

    ```python hl_lines="10"
    --8<-- "locks_and_rate_limits/fail_open_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="10"
    --8<-- "locks_and_rate_limits/fail_open_async.py:show"
    ```

!!! warning "`limited` always fails open"

    `fail_open` is an option of `count` only: a function of `limited` lets its call through when
    the backend fails. Call `count` where the limit must fail closed.

## Rate limits of HTTP requests

Two ways count the requests of a web application with a limit of this page.
[`RateLimitMiddleware`][pashe.asgi.RateLimitMiddleware] of `pashe.asgi` limits the whole
application in any ASGI framework, or one route of Starlette or Litestar; for one route of FastAPI,
or a limit by a user other dependencies give, take [`rate_limit`](web/fastapi.md) of
`pashe.contrib.fastapi`. They count the same, and tell what is left in the same `RateLimit-Limit`,
`RateLimit-Remaining` and `RateLimit-Reset` headers.

The middleware runs before the route: a request over the limit gets `429 Too Many Requests` with
`Retry-After` from it, and the application never sees it. Its
[`key`][pashe.asgi.RateLimitMiddleware(key)] is a function of the ASGI scope: the address of the
client, a header, or `scope["user"]` when an authentication middleware ran before it. The
dependency of FastAPI runs with the route, takes the `Request` and what other dependencies made,
such as the current user, and raises `RateLimitedError` for a handler of yours to answer in the
format of your API.

### The whole application

=== "Starlette"

    ```python hl_lines="18 19 20 29"
    --8<-- "web/rate_limit_starlette.py:show"
    ```

=== "FastAPI"

    ```python
    --8<-- "web/rate_limit_fastapi.py"
    ```

The 101st request within the minute:

```console hl_lines="2 3"
$ curl -i http://localhost:8000/search -H 'X-Forwarded-For: 203.0.113.7'
HTTP/1.1 429 Too Many Requests
retry-after: 19
content-type: text/plain; charset=utf-8
content-length: 17

Too Many Requests
```

### One route

=== "Litestar"

    ```python hl_lines="20 21 29"
    --8<-- "web/rate_limit_litestar.py:show"
    ```

=== "Starlette"

    ```python
    --8<-- "web/rate_limit_route_starlette.py:show"
    ```

=== "FastAPI"

    ```python
    --8<-- "web/rate_limit_route_fastapi.py:show"
    ```

!!! note "mypy and Litestar"

    Litestar types ASGI with TypedDicts, while Starlette, httpx and pashe type it with
    mappings, so mypy refuses any ASGI middleware of the Starlette kind in `DefineMiddleware`:
    the `type: ignore` above says so. It runs as it is.

!!! warning "`key` is required"

    Behind a proxy the address of the connection is the address of the proxy: take the client
    from a header your proxy sets.

## Every option

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_options_async.py:show"
    ```
