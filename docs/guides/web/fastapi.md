# FastAPI

[`rate_limit`][pashe.contrib.fastapi.rate_limit] from `pashe.contrib.fastapi`, in the `fastapi`
extra, is a dependency. It counts a route's requests with an
[`AsyncRateLimiter`][pashe.AsyncRateLimiter] from `pashe`.

```python hl_lines="10 29 31 33 41 42 45"
--8<-- "web/fastapi_async.py:show"
```

`rate_limit` counts every request to the route. It tells the client what's left in
`RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset`. Over the limit, it raises
[`RateLimitedError`][pashe.errors.RateLimitedError].
[`OverloadedError`][pashe.errors.OverloadedError] comes from
[`Stampede.max_loads`][pashe.options.Stampede(max_loads)].

Answer both with your own handlers, in the error format your API already uses. Above, they're a
`429` with `Retry-After`, and a `503`.

A request within the limit shows how much is left:

```console hl_lines="5 6 7"
$ curl -i 'http://localhost:8000/search?query=kettle' -H 'X-Forwarded-For: 203.0.113.7'
HTTP/1.1 200 OK
content-length: 10
content-type: application/json
ratelimit-limit: 100
ratelimit-remaining: 99
ratelimit-reset: 18

[{"id":1}]
```

The 101st request within the minute is refused by the `RateLimitedError` handler above:

```console hl_lines="2 3"
$ curl -i 'http://localhost:8000/search?query=kettle' -H 'X-Forwarded-For: 203.0.113.7'
HTTP/1.1 429 Too Many Requests
retry-after: 19
content-length: 46
content-type: application/json

{"detail":"rate limited, retry after 18.351s"}
```

!!! tip "The whole application"

    To limit every request, add `RateLimitMiddleware` from `pashe.asgi` with
    `app.add_middleware(...)`: see [Rate limits for HTTP](../rate-limits.md#rate-limits-of-http-requests).

!!! warning "`key` is required"

    Behind a proxy, the connection's address is the proxy's address. Make
    [`key`][pashe.contrib.fastapi.rate_limit(key)] read the client from a header your proxy sets.
