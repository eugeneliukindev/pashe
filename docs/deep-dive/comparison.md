# pashe and other libraries

How pashe compares with the caching libraries Python services take most often. The other columns
come from the releases on PyPI as of November 2026: cachetools 8.0.3, aiocache 0.12.3, cashews
7.6.0 and dogpile.cache 1.5.0, read in their docs and their source.

## What each has

| | pashe | cachetools | aiocache | cashews | dogpile.cache |
| --- | --- | --- | --- | --- | --- |
| Sync and async | both, one API | sync | async | async | sync |
| Shared by processes | Redis, Redis Cluster, SQLite | no, memory of the process | Redis, Memcached | Redis, Redis Cluster, a disk cache | Redis, Redis Cluster, Valkey, Memcached, DBM files |
| Memcached | no | no | yes | no | yes |
| Keys from templates | `"user:{user.id}"`, with digests | a key function | a key function | `"user:{user.id}"` | a key function |
| Invalidating a group | tags: two calls per tag, no set of keys kept | no | no | tags: a set of keys kept per tag | a whole region at once |
| Stale results | while revalidating, on an error, when slow; reload before the TTL | no | no | an early refresh, on an error | while one caller reloads |
| Stampedes, in a process | one load per key, a limit of loads at once | with a lock you give | `@cached_stampede`: a lock in the backend | one load per key | one load per key |
| Stampedes, across processes | a lock in the backend | no | a lock in the backend | a lock in the backend | a lock in Redis, Valkey or Memcached |
| Locks and rate limits | both, with ASGI, WSGI and FastAPI | no | locks marked as not for consistency | both, and a circuit breaker | no |
| Near cache | in front of any backend, by pub/sub or by Redis client tracking | no | no | Redis client-side caching | no |
| Negative caching | the errors you name, for a TTL of their own | caches `None` | a cached `None` is a miss | caches `None` and errors | caches `None` |
| A failing backend | a fallback in memory, a circuit breaker | no | no | a circuit breaker decorator | no |
| Metrics | Prometheus, OpenTelemetry, Sentry, logging | hit and miss counts | plugins for timing and hit ratio | middleware, Prometheus | logging |
| Typed | `py.typed`, the signature of your function kept | `py.typed` | no, in the release | `py.typed` | `py.typed` |
| Values | JSON, orjson, msgspec, pydantic, signed pickle; gzip, zstd | objects in memory | JSON, pickle, msgpack | pickle, JSON; gzip, zlib | pickle, or what you give |

## When another library fits better

- **One process, and nothing else:** cachetools. It keeps objects as they are, without encoding
  them, and needs no backend.
- **Memcached:** dogpile.cache or aiocache. pashe has no Memcached backend, as [Choosing a
  backend](../guides/backends/index.md#every-store) tells why.
- **A large sync codebase on dogpile.cache:** its regions and their invalidation are mature, and
  moving them buys little.
- **Async code and a disk cache through `diskcache`:** cashews. pashe keeps entries on disk with
  its SQLite backend instead.

## Where pashe differs

- **One API for sync and async code.** A service with both, such as a web app and its workers,
  uses one cache and one set of options.
- **A tag costs the same however many entries it covers.** A tag is a counter whose generation
  every entry remembers: an invalidation bumps the counter, and no list of keys has to be kept,
  read or deleted. See
  [Core concepts](../concepts.md#tags).
- **Failure is part of the design.** Stale results answer while the source fails or hangs, a
  fallback keeps loads from reaching the source while Redis is down, and a circuit breaker stops
  waiting on a backend that is gone.
- **The type of a result is kept.** A stored result decodes as the return annotation, and a type
  the codec cannot rebuild is refused when the function is decorated. See [Types](../guides/caching/types.md).

pashe is not released yet: its API may still change, as the [changelog](changelog.md) says.
