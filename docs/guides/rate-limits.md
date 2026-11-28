# Rate limits

You want each client to make at most so many calls, however many processes serve them.
[`RateLimiter`][pashe.RateLimiter], from `pashe`, counts calls for a key in a backend, so every
process that uses it shares the count. Calls over the limit get
[`RateLimitedError`][pashe.errors.RateLimitedError]. [`AsyncRateLimiter`][pashe.AsyncRateLimiter]
is the async side.

- A limit is a [sliding window](#a-sliding-window) or a
  [fixed window with a ban](#a-fixed-window-and-a-ban).
- A call can [weigh more](#a-heavy-call) than others.
- When the [backend fails](#when-the-backend-fails), calls get through.
- [HTTP requests](#rate-limits-of-http-requests) are limited by a middleware or a FastAPI
  dependency.

The counters don't mix with a cache's entries, even over the same backend and `prefix`. The
limiter doesn't close anything: the backend belongs to whoever created it.

!!! info "Where it works"

    In the backend. Over Redis that's every process on every machine, over SQLite every process
    on one machine, and over memory one process. See
    [Where each feature works](choosing.md#where-each-feature-works).

## Counting a call and limiting a function

[`limiter.count`][pashe.RateLimiter.count] counts one call for a key you choose, such as a
client's address. [`@limiter.limited`][pashe.RateLimiter.limited] counts every call of a function.
Its [`key`][pashe.RateLimiter.limited(key)] is a template over the arguments, the same as for
`@cache`. Without a key, the function has one counter for all calls.

=== "Sync"

    ```python hl_lines="19 25"
    --8<-- "locks_and_rate_limits/rate_limit_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="19 25"
    --8<-- "locks_and_rate_limits/rate_limit_async.py:show"
    ```

A call over the limit raises `RateLimitedError`. Its `retry_after` is what you put in a
`Retry-After` header. `count` returns a [`RateLimitState`][pashe.ratelimit.RateLimitState]: how
much of the limit is left.

Each limit has its own counters, named by the key and the limit. Say one address has two limits:
10 calls a minute and 100 an hour. They count separately, and a call passes only when both let it.
If you use the same limit in two places with the same key, they share counters.

!!! warning "A limit is checked in a few calls to the backend, not at once"

    A sliding window adds the call to its counter, reads the last window, and takes the call
    back if it's over the limit. A fixed window adds the call, then reads or sets the time left.
    In between, other processes already see the call counted. So under a burst right at the limit,
    a few calls may be refused that a single check would let through. Calls over the limit never
    get through.

## A sliding window

With [`SlidingWindow`][pashe.ratelimit.SlidingWindow], about `calls` calls pass in any span of
`per` seconds, even across the boundary between two windows.

=== "Sync"

    ```python hl_lines="11"
    --8<-- "locks_and_rate_limits/sliding_window_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="11"
    --8<-- "locks_and_rate_limits/sliding_window_async.py:show"
    ```

Refused calls aren't counted. So a client that keeps calling over the limit gets through again as
soon as the span has room.

## A fixed window and a ban

Want a client who goes over to wait longer? With [`FixedWindow`][pashe.ratelimit.FixedWindow],
`calls` calls pass per window, and the window starts with the first call. The first call over the
limit blocks the key for `ban_for`. If you don't set `ban_for`, the ban lasts as long as the
window.

=== "Sync"

    ```python hl_lines="11"
    --8<-- "locks_and_rate_limits/fixed_window_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="11"
    --8<-- "locks_and_rate_limits/fixed_window_async.py:show"
    ```

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 20" data-start="0"><b>calls 1 to 5</b><br>pass</div>
<div class="pashe-timeline__source" style="flex: 300" data-start="20 s"><b>call 6 bans the key</b><br>every call raises RateLimitedError</div>
<div class="pashe-timeline__fresh" data-start="320 s"><b>the next call</b><br>starts a new window</div>
</div>

## A heavy call

Some calls cost your source more than others, such as an exact search. Give such a call a
[`cost`][pashe.RateLimiter.count(cost)], and it counts as that many calls.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "locks_and_rate_limits/cost_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "locks_and_rate_limits/cost_async.py:show"
    ```

## When the backend fails

When the backend fails, the call gets through uncounted, and the error goes to `on_error`. A
broken rate limit shouldn't take your service down.

But when a limit guards against abuse, such as for logins or password resets, you want it to fail
closed. Turn [`fail_open`][pashe.RateLimiter.count(fail_open)] off, and a failing backend raises
[`BackendError`][pashe.errors.BackendError].

=== "Sync"

    ```python hl_lines="14"
    --8<-- "locks_and_rate_limits/fail_open_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "locks_and_rate_limits/fail_open_async.py:show"
    ```

!!! warning "`limited` always fails open"

    Only `count` has `fail_open`. A function decorated with `limited` lets its calls through
    when the backend fails. Call `count` wherever the limit must fail closed.

## Rate limits of HTTP requests

There are two ways to apply the limits from this page to a web application:

- [`RateLimitMiddleware`][pashe.asgi.RateLimitMiddleware], from `pashe.asgi`, limits the whole
  application in any ASGI framework, or one route in Starlette or Litestar.
- [`rate_limit`](web/fastapi.md), from `pashe.contrib.fastapi`, limits one FastAPI route, or limits
  by a user that other dependencies give you.

Both count the same way. Both report what's left in the same `RateLimit-Limit`,
`RateLimit-Remaining` and `RateLimit-Reset` headers.

The middleware runs before the route. A request over the limit gets `429 Too Many Requests` with
`Retry-After`, and your application never sees it. Its
[`key`][pashe.asgi.RateLimitMiddleware(key)] is a function of the ASGI scope: the client's
address, a header, or `scope["user"]` when an authentication middleware ran first.

The FastAPI dependency runs with the route. It takes the `Request` and whatever other dependencies
produced, such as the current user. It raises `RateLimitedError`, and your handler turns it into a
response in your API's format.

### The whole application

=== "Starlette"

    ```python hl_lines="21 22 23 32"
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

    ```python hl_lines="23 24 32"
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

    Litestar types ASGI with TypedDicts, while Starlette, httpx and pashe type it with mappings.
    So mypy refuses any Starlette-style ASGI middleware in `DefineMiddleware`, which is what the
    `type: ignore` above is for. The code runs fine as it is.

!!! warning "`key` is required"

    Behind a proxy, the connection's address is the proxy's address. Take the client from a
    header your proxy sets.

## Every option

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/rate_limit_options_async.py:show"
    ```
