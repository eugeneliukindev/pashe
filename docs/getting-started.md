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

The HTTP caching middlewares of `pashe.asgi` and `pashe.wsgi`, and `RateLimitMiddleware` of `pashe.asgi` for Starlette, Litestar and any ASGI application, need no extra.

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
when the application stops, or use it as a context manager: it closes its backend.

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

```{.console title="What the cache keeps in Redis"}
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

## LLMs support

Do you write code with an AI assistant? These files give it the docs as context:

- [`llms.txt`](llms.txt): an index with a link to every page;
- [`llms-full.txt`](llms-full.txt): the complete docs in one file;
- every page as Markdown: press **Copy as Markdown** next to its title.

## Next

The guides run in the order you meet the API, each built on those before it:

- [Core concepts](concepts.md): how a cached call is answered.
- [What to choose](guides/choosing.md): which backend, near cache, bus, codec and options for your case.
- [Caching functions](guides/caching/decorator.md): the decorator, keys, what is stored, types, batches, values.
- [Invalidation](guides/invalidation/tags.md): tags, and invalidating on a write.
- [Backends](guides/backends/index.md): memory, Redis, a cluster, and near caches.
- [Encoding](guides/values/codecs.md): codecs and compressors.
- [Failures and load](guides/failures/stale.md): stale results, a failing backend, stampedes.
- [Observability](guides/observability/hooks.md): hooks, logs, OpenTelemetry and Prometheus.
- [Locks and rate limits](guides/locks/locks.md).
- [Web](guides/web/headers.md): HTTP caching headers, whole responses, FastAPI.
- [Recommended setup](guides/recommended-setup.md): what to install and configure for production.
