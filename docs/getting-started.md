# Getting started

## Install

pashe needs Python 3.12 or later and nothing else: every integration is an extra.

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

The HTTP caching middlewares of `pashe.asgi` and `pashe.wsgi`, and `RateLimitMiddleware` of
`pashe.asgi` for Starlette, Litestar and any ASGI application, need no extra.

!!! tip "Pick a codec that rebuilds your types"

    The default `JsonCodec` stores what JSON holds as it is: dicts, lists, strings and numbers, and
    a `TypedDict`. A function that returns a dataclass or a model is refused when it is
    decorated. When your functions return those, install `msgspec` or `pydantic` and give the cache their codec: see
    [Recommended setup](guides/recommended-setup.md).

!!! note

    Importing a module of an extra that is not installed raises `MissingExtraError`, a `ModuleNotFoundError`, with the
    command that installs it.

## A cache

A cache stores entries in a backend. In production that is Redis, shared by every process; in
tests and on a single process it can be memory:

=== "Sync"

    ```python
    --8<-- "getting_started/cache_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/cache_async.py"
    ```

`prefix` goes in front of every key, so several services can share one Redis. Close the cache
when the application stops, or use it as a context manager: it closes its backend and its
fallback, each even when another fails to close. A script takes the block of `with`; an
application closes it in its lifespan, here of FastAPI:

=== "Sync"

    ```python
    --8<-- "getting_started/close_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/close_async.py"
    ```

## A cached function

Decorate a function with the cache; its arguments make the key, its return annotation says what
the stored value decodes as:

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

The result lives in Redis under the prefix and the key, for the TTL:

```console title="What the cache keeps in Redis"
$ redis-cli KEYS 'app:*'
1) "app:user:1"
$ redis-cli TTL app:user:1
(integer) 300
```

The cached function keeps the signature of the function and adds three methods:

=== "Sync"

    ```python
    --8<-- "getting_started/function_sync.py:methods"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/function_async.py:methods"
    ```

## Keep it fresh

Results change at the source. Drop them when you change the data, or let them expire:

=== "Sync"

    ```python
    --8<-- "getting_started/fresh_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "getting_started/fresh_async.py:show"
    ```

## Next

The guides run in the order you meet the API, each built on those before it:

- [Core concepts](concepts.md): how a cached call is answered, and where each feature works.
- [Glossary](glossary.md): the words these docs use, one for each thing.
- [Caching functions](guides/caching/decorator.md): the decorator, keys, what is stored, types, batches, values.
- [Freshness](guides/failures/stale.md): stale results, and stampedes of callers that miss at once.
- [Invalidation](guides/invalidation/tags.md): tags, and invalidating on a write.
- [Backends](guides/backends/index.md): memory, SQLite, Redis, a cluster, near caches, and a backend that fails.
- [Encoding](guides/values/codecs.md): codecs and compressors.
- [Locks](guides/locks/locks.md) and [rate limits](guides/locks/rate-limits.md), of calls and of HTTP requests.
- [Observability](guides/observability/hooks.md): hooks, logs, OpenTelemetry, Prometheus and Sentry.
- [Web](guides/web/headers.md): HTTP caching headers, whole responses, FastAPI.
- [In production](guides/choosing.md): what to choose for each part, and the recommended setup.
