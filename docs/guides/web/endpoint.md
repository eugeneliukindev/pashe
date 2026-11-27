# Caching an endpoint

Decorate the endpoint itself with `@cache(...)`, under its route decorator. The framework still
routes, validates and serializes, and the endpoint's body runs once per key and TTL.

Add [`CacheHeadersMiddleware`][pashe.asgi.CacheHeadersMiddleware] from `pashe.asgi`, or from
`pashe.wsgi`, with [`cache_control`][pashe.asgi.CacheHeadersMiddleware(cache_control)] set to
`"public"`. It uses the cached call's TTL to tell clients, proxies and CDNs how long the response
stays fresh.

```python hl_lines="18 19 21 25 26 32"
--8<-- "web/endpoint_async.py:show"
```

- The endpoint's parameters fill the key, as for any cached function. Put everything that
  changes the response into the key, such as `lang` here. A parameter the framework injects, such
  as a `Request`, stays out of it.
- `stale`, `stampede`, `negative`, tags and a `Fallback` work as for any cached function, and the
  hooks see every call.
- The cache's codec stores what the endpoint returns. Use
  [`PydanticCodec`][pashe.contrib.pydantic.PydanticCodec] for pydantic models and
  [`MsgspecJsonCodec`][pashe.contrib.msgspec.MsgspecJsonCodec] for dataclasses. The default,
  [`JsonCodec`][pashe.codecs.JsonCodec], holds plain `dict`s and `list`s.

!!! warning "Public only when it's the same for every user"

    `cache_control="public"` lets shared caches keep the response. If a response depends on who
    asks, leave the default `"private"`. Also put who asks into the key, or the endpoint gives
    everyone one user's result.

## What a client sees

The first request runs the endpoint. The next one is answered from the cache:

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

After `rename(1)`, `invalidate_tags("product:1")` drops the product in every language. The next
request is a miss and runs the endpoint again.

## Whole responses

pashe caches what endpoints return, not HTTP responses. Want to keep whole responses, such as
rendered HTML? Put a proxy or a CDN in front of your service, such as nginx, Varnish or
Cloudflare. It keeps a response as long as its `Cache-Control` says, and `CacheHeadersMiddleware`
sets that header. Or use your framework's cache: Django's `cache_page`, or `cache=` on a Litestar
route.
