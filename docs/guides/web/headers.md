# HTTP caching headers

A middleware adds the headers of caching to every successful `GET` response: WSGI for a sync
application, ASGI for an async one.

=== "Sync"

    ```python hl_lines="9 10 24"
    --8<-- "web/wsgi_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="8 9 11"
    --8<-- "web/headers_fastapi.py:show"
    ```

| Header | When | Value |
| --- | --- | --- |
| `ETag` | every successful `GET` | a hash of the body; a request whose `If-None-Match` names it is answered `304` without the body |
| `Cache-Control` | the endpoint made cached calls and set none itself | `private, max-age=` the shortest TTL of its results; `no-cache` once one is stale |
| `Cache-Status` | the endpoint made cached calls | `pashe; hit; ttl=60` or `pashe; fwd=miss; ttl=60`, as RFC 9211 says |

## What a client sees

The FastAPI service of the Async tab above, one cached function behind an endpoint, answers so.
The first request runs `get_product`: a miss, fresh for the 60 seconds of its TTL, less the time
the request took.

```console hl_lines="5 6 7"
$ curl -i http://localhost:8000/products/1
HTTP/1.1 200 OK
content-length: 24
content-type: application/json
etag: "a761cd8c95a5db71c678ea1e5c290d8a"
cache-control: private, max-age=59
cache-status: pashe; fwd=miss; ttl=59

{"id":1,"name":"Kettle"}
```

The next one is answered from the cache: the same body, so the same `ETag`.

```console hl_lines="7"
$ curl -i http://localhost:8000/products/1
HTTP/1.1 200 OK
content-length: 24
content-type: application/json
etag: "a761cd8c95a5db71c678ea1e5c290d8a"
cache-control: private, max-age=59
cache-status: pashe; hit; ttl=59

{"id":1,"name":"Kettle"}
```

A client that kept the response asks with its `ETag`, and gets `304` without the body: the
endpoint still runs, the body does not travel.

```console hl_lines="2"
$ curl -i http://localhost:8000/products/1 -H 'If-None-Match: "a761cd8c95a5db71c678ea1e5c290d8a"'
HTTP/1.1 304 Not Modified
etag: "a761cd8c95a5db71c678ea1e5c290d8a"
cache-control: private, max-age=59
cache-status: pashe; hit; ttl=59
```

The server adds headers of its own, such as `date` and `server`; they are left out here.

How the middleware picks `Cache-Control`, when the endpoint set none:

```mermaid
flowchart LR
    response(["a 200 response to GET"]) --> calls{"cached calls?"}
    calls -- "none" --> etag["ETag only"]
    calls -- "every result fresh for 1 s or more" --> fresh["Cache-Control: private, max-age = the shortest TTL"]
    calls -- "one stale or not stored" --> stale["Cache-Control: private, no-cache"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class fresh fromCache
    class stale fromSource
```

The middleware learns of the cached calls of a request from a `CacheHeadersHook` of `pashe.hooks`:
give the same hook to every cache the application calls and to the middleware, and the code of
the endpoint does not change. The calls of a cache without the hook are left out of
`Cache-Control` and `Cache-Status`; `ETag` and `304` work either way. The ETag is a hash of the response, not of a cached value, so it is right whatever
else the response holds.

!!! warning "Responses are private by default"

    `cache_control="private"` lets only the client keep a response, as cached data may belong to
    one user. Give `cache_control="public"` only when responses are the same for everyone:
    shared caches and proxies then keep them too.

## A request that asks for fresh data

A browser on a hard reload, or `curl -H 'Cache-Control: no-cache'`, asks past every stored
response; `Pragma: no-cache` of HTTP/1.0 too. The middleware lets such a request through to the
source only if `allow_no_cache` says so: its cached calls then load, store what they loaded for
the requests after it, and answer `Cache-Status: pashe; fwd=request`. Any other request with the
header is answered from the cache, as if it had none.

```python hl_lines="17 18 21"
--8<-- "web/no_cache_fastapi.py:show"
```

```console hl_lines="3 6"
$ curl -si http://localhost:8000/products/1 -H 'Cache-Control: no-cache' | grep cache-status
cache-status: pashe; hit; ttl=59
$ curl -si http://localhost:8000/products/1 -H 'Cache-Control: no-cache' -H 'X-Role: staff' | grep cache-status
cache-status: pashe; fwd=request; ttl=60
```

`Cache-Control: max-age=0`, which a browser sends on a plain reload, does not count. In code,
`with pashe.no_cache():` does the same for every cached call in the block.

!!! warning "Any client can send the header"

    Every request allowed loads from the source, so a client allowed to would bypass the cache
    at will. None is by default: let only those you trust, such as staff behind your login.

!!! note "A 304 still runs the endpoint"

    The ETag is a hash of the body, so the endpoint runs to know it; a `304` saves the transfer.
    A streamed response passes as it is, and so does a WSGI response without `Content-Length`.

---

API reference: [`pashe.asgi` and `pashe.wsgi`](../../reference/http.md), [`pashe.hooks`](../../reference/hooks.md).
