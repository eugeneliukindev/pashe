# Caching an endpoint

Decorate the endpoint itself with `@cache(...)`, under the decorator of its route: the
framework still routes, validates and serializes, and the body of the endpoint runs once per key
and TTL. `CacheHeadersMiddleware` with `cache_control="public"` tells clients, proxies and CDNs
how long the response stays fresh, from the TTL of the cached call.

```python hl_lines="18 19 21 25 26 32"
--8<-- "web/endpoint_async.py:show"
```

- The parameters of the endpoint fill the key, as for any cached function. Put in the key all
  that changes the response, such as `lang` here; a parameter the framework injects, such as a
  `Request`, stays out of it.
- `stale`, `stampede`, `negative`, tags and a `Fallback` work as for any cached function, and the
  hooks see every call.
- The codec of the cache stores what the endpoint returns: `PydanticCodec` for pydantic models,
  `MsgspecJsonCodec` for dataclasses; `JsonCodec`, the default, holds plain `dict`s and `list`s.

!!! warning "Public only when it is the same for every user"

    `cache_control="public"` lets shared caches keep the response. Leave the default
    `"private"` when a response depends on who asks; and put who asks in the key, or the endpoint
    answers everyone with the result of one user.

## What a client sees

The first request runs the endpoint, the next one is answered from the cache:

```console hl_lines="6 7"
$ curl -i 'http://localhost:8000/products/1?lang=ru'
HTTP/1.1 200 OK
content-length: 36
content-type: application/json
etag: "07551772f8aefaa87ab859d7766e66c1"
cache-control: public, max-age=59
cache-status: pashe; fwd=miss; ttl=59

{"id":1,"name":"Kettle","lang":"ru"}
$ curl -i 'http://localhost:8000/products/1?lang=ru'
HTTP/1.1 200 OK
content-length: 36
content-type: application/json
etag: "07551772f8aefaa87ab859d7766e66c1"
cache-control: public, max-age=59
cache-status: pashe; hit; ttl=59

{"id":1,"name":"Kettle","lang":"ru"}
```

After `rename(1)`, `invalidate_tags("product:1")` drops every language of the product: the next
request runs the endpoint again, a miss.

## Whole responses

pashe caches what endpoints return, not HTTP responses. To keep whole responses, such as
rendered HTML, put a proxy or a CDN in front of the service, such as nginx, Varnish or Cloudflare:
it keeps a response as long as its `Cache-Control` says, which `CacheHeadersMiddleware` sets. Or
take the cache of your framework: `cache_page` of Django, `cache=` of a route in Litestar.

---

API reference: [`pashe.asgi` and `pashe.wsgi`](../../reference/http.md), [`pashe`](../../reference/caches.md).
