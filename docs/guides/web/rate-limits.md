# Rate limits for HTTP

Two ways count the requests of a web application with a [rate limit](../locks/rate-limits.md)
of the cache. They count the same, and tell what is left in the same `RateLimit-Limit`,
`RateLimit-Remaining` and `RateLimit-Reset` headers.

| What | Take | Where |
| --- | --- | --- |
| the whole application, in any ASGI framework, FastAPI too | `RateLimitMiddleware` of `pashe.asgi` | `app.add_middleware(...)`, or the middleware list of the application |
| one route of Starlette or Litestar | `RateLimitMiddleware` | the middleware of the route |
| one route of FastAPI, or a limit by a user of other dependencies | [`rate_limit`](fastapi.md) of `pashe.contrib.fastapi` | `dependencies=[Depends(rate_limit(...))]` |

`RateLimitMiddleware` runs before the route: a request over the limit gets `429 Too Many Requests`
with `Retry-After` from it, and the application never sees it. Its key is a function of the ASGI
scope: the address of the client, a header, or `scope["user"]` when an authentication middleware
ran before it. The dependency of FastAPI runs with the route, takes the `Request` and what other
dependencies made, such as the current user, and raises `RateLimitedError` for a handler of yours
to answer in the format of your API.

## The whole application

=== "Starlette"

    ```python hl_lines="18 19 20 29"
    --8<-- "web/rate_limit_starlette.py:show"
    ```

=== "FastAPI"

    ```python
    app.add_middleware(RateLimitMiddleware, cache=cache, limit=per_minute(100), key=client)
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

## One route

=== "Litestar"

    ```python hl_lines="20 21 29"
    --8<-- "web/rate_limit_litestar.py:show"
    ```

=== "Starlette"

    ```python
    Route("/login", login, middleware=[Middleware(RateLimitMiddleware, cache=cache, limit=logins, key=client)])
    ```

=== "FastAPI"

    ```python
    @app.get("/login", dependencies=[Depends(rate_limit(cache, logins, key=client_key))])
    ```

!!! note "mypy and Litestar"

    Litestar types ASGI with TypedDicts, while Starlette, httpx and pashe type it with
    mappings, so mypy refuses any ASGI middleware of the Starlette kind in `DefineMiddleware`:
    the `type: ignore` above says so. It runs as it is.

!!! warning "`key` is required"

    Behind a proxy the address of the connection is the address of the proxy: take the client
    from a header your proxy sets.

---

API reference: [`pashe.asgi`](../../reference/http.md), [`pashe.contrib.fastapi`](../../reference/contrib/fastapi.md).
