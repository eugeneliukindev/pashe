# Getting started

## Install

pashe needs Python 3.12 or later and nothing else. Every integration comes as an extra.

=== ":simple-uv:{ .brand-uv } uv"

    ```sh
    uv add pashe
    ```

=== ":simple-poetry:{ .brand-poetry } poetry"

    ```sh
    poetry add pashe
    ```

=== ":simple-pypi:{ .brand-pypi } pip"

    ```sh
    pip install pashe
    ```

Extras for backends and buses:

| Extra | What it brings |
| --- | --- |
| `"pashe[redis]"` | :simple-redis:{ .brand-redis } Redis and Valkey backends and invalidation buses: `pashe.contrib.redis` |

Extras for codecs and compression:

| Extra | What it brings |
| --- | --- |
| `"pashe[msgspec]"` | the fastest codecs, which rebuild dataclasses and `msgspec.Struct`s |
| `"pashe[pydantic]"` | a codec that rebuilds pydantic models |
| `"pashe[orjson]"` | a fast JSON codec |
| `"pashe[zstd]"` | the zstd compressor, from the standard library on Python 3.14 |

Extras for web frameworks:

| Extra | What it brings |
| --- | --- |
| `"pashe[fastapi]"` | :simple-fastapi:{ .brand-fastapi } rate limits of routes and their HTTP errors |

Extras for metrics and errors:

| Extra | What it brings |
| --- | --- |
| `"pashe[opentelemetry]"` | the metrics of caches through the OpenTelemetry API: `pashe.contrib.opentelemetry` |
| `"pashe[prometheus]"` | the same metrics through `prometheus_client`: `pashe.contrib.prometheus` |
| `"pashe[sentry]"` | the errors caches work around as breadcrumbs in Sentry: `pashe.contrib.sentry` |
| `"pashe[all]"` | every extra |

You don't need an extra for the HTTP caching middlewares in `pashe.asgi` and `pashe.wsgi`. The
same goes for `RateLimitMiddleware` in `pashe.asgi`, which works with Starlette, Litestar and any
ASGI application.

!!! tip "Pick a codec that rebuilds your types"

    The default `JsonCodec` stores what JSON can hold, as it is: dicts, lists, strings, numbers
    and `TypedDict`s. If a function returns a dataclass or a model, the decorator refuses it. Do
    your functions return those? Install `msgspec` or `pydantic` and give the cache their codec, as
    [Recommended setup](guides/recommended-setup.md) shows.

!!! note

    If you import a module whose extra isn't installed, you get `MissingExtraError`, a
    `ModuleNotFoundError`. Its message tells you the command that installs the extra.

## A cache

A cache stores its entries in a backend. In production that's Redis, which every process
shares. In tests, or in a single process, memory works too:

=== "Sync"

    ```python
    --8<-- "getting_started/cache_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/cache_async.py"
    ```

!!! warning "redis-py before 8: pass `socket_timeout`"

    A redis-py 8 client waits at most 5 seconds for Redis, so the examples in these docs leave
    the timeout out. Before version 8, a client waits forever, and the backend refuses it. Create
    it as `Redis.from_url(url, socket_timeout=1)`.

`prefix` goes in front of every key, so several services can share one Redis.

Close the cache when your application stops, or use it as a context manager. It closes its
backend and its fallback, and it closes each one even if the other fails to close. In a script,
use a `with` block. In an application, close the cache in its lifespan, as here with FastAPI:

=== "Sync"

    ```python
    --8<-- "getting_started/close_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/close_async.py"
    ```

## A cached function

Decorate a function with the cache. Its arguments make the key, and its return annotation tells
pashe what type the stored result decodes to:

=== "Sync"

    ```python
    --8<-- "getting_started/function_sync.py:function"
    --8<-- "getting_started/function_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/function_async.py:function"
    --8<-- "getting_started/function_async.py:calls"
    ```

The result lives in Redis under the prefix and the key, until its TTL ends:

```console title="What the cache keeps in Redis"
$ redis-cli KEYS 'app:*'
1) "app:user:1"
$ redis-cli TTL app:user:1
(integer) 300
```

The cached function keeps your function's signature and adds three methods:

=== "Sync"

    ```python
    --8<-- "getting_started/function_sync.py:methods"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/function_async.py:methods"
    ```

## Keep it fresh

Your data changes at the source. When you change it, drop the cached results, or let them
expire:

=== "Sync"

    ```python
    --8<-- "getting_started/fresh_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/fresh_async.py:show"
    ```

## Next

The guides follow the order in which you'll meet the API, one page for each part:

- [Core concepts](concepts.md): how pashe answers a cached call, and where each feature works.
- [What to choose](guides/choosing.md): which part fits each need, and where it works.
- [Caching functions](guides/caching/decorator.md): the decorator, keys, the TTL, types, batches, values.
- [Tags and invalidation](guides/tags.md): drop a group of results, and invalidate on a write.
- [Stale results](guides/stale.md), [stampede protection](guides/stampedes.md),
  [negative caching](guides/negative.md) and [storing only some results](guides/store.md): the
  options of `@cache`, one page each.
- [Fallback and breaker](guides/fallback.md): when the backend fails.
- [Backends](guides/backends/index.md) and the [near cache](guides/near-cache.md): memory, SQLite, Redis, a cluster, copies in memory.
- [Codecs](guides/codecs.md) and [compressors](guides/compressors.md): how values are stored.
- [Locks](guides/locks.md) and [rate limits](guides/rate-limits.md): for calls and for HTTP requests.
- [Hooks](guides/observability/hooks.md): logs, OpenTelemetry, Prometheus and Sentry.
- [HTTP](guides/web/headers.md): caching headers, whole responses, FastAPI.
- [In production](guides/recommended-setup.md): the recommended setup, a whole shop as an example, and troubleshooting.
