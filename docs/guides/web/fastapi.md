# FastAPI

`rate_limit` of `pashe.contrib.fastapi`, the `fastapi` extra, is a dependency that counts the
requests of a route with a `RateLimiter` of `pashe`, an `AsyncRateLimiter`.

```python hl_lines="10 27 29 31 39 40 43"
--8<-- "web/fastapi_async.py:show"
```

`rate_limit` counts every request of the route and tells what is left in `RateLimit-Limit`,
`RateLimit-Remaining` and `RateLimit-Reset`. Over the limit it raises `RateLimitedError`, and
`OverloadedError` comes from `Stampede.max_loads`: answer them with handlers of your own, in the
format of errors your API already has; above they are `429` with `Retry-After`, and `503`.

A request within the limit says what is left of it:

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

The 101st within the minute is refused by the handler of `RateLimitedError` above:

```console hl_lines="2 3"
$ curl -i 'http://localhost:8000/search?query=kettle' -H 'X-Forwarded-For: 203.0.113.7'
HTTP/1.1 429 Too Many Requests
retry-after: 19
content-length: 46
content-type: application/json

{"detail":"rate limited, retry after 18.351s"}
```

!!! tip "The whole application"

    To limit every request, take `RateLimitMiddleware` of `pashe.asgi` with
    `app.add_middleware(...)`: see [Rate limits for HTTP](rate-limits.md).

!!! warning "`key` is required"

    Behind a proxy the address of the connection is the address of the proxy: take the client
    from a header your proxy sets.

---

API reference: [`rate_limit`](../../reference/contrib/fastapi.md#pashe.contrib.fastapi.rate_limit).
