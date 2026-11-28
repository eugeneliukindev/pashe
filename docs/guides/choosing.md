# What to choose

Every part of a cache comes with a few options. Each table below answers "which one?" for one
part: find what you have, and it tells you what to take. Each part's own page tells you the rest.

## Where each feature works

A feature that lives in the backend works for every process that uses that backend. A feature
that lives in the cache works only in its own process, as
[Core concepts](../concepts.md#where-each-feature-works) explains. Each cell tells you which
processes share the feature.

| Feature | Lives in | Over Redis or Valkey | Over SQLite | Over memory |
| --- | --- | --- | --- | --- |
| cached results | the backend | all machines | one machine | one process |
| tags and `invalidate_tags` | the backend | all machines | one machine | one process |
| `Locks`: `lock`, `try_lock` and `@locked` | the backend | all machines | one machine | one process |
| `RateLimiter`: `count` and `@limited` | the backend | all machines | one machine | one process |
| `Stampede.lock_for` | the backend | all machines | one machine | one process, `share_loads` is cheaper |
| `Stampede.revalidate_before` | the backend | all machines | one machine | one process |
| `Stampede.share_loads` | the cache | one process | one process | one process |
| `Stampede.max_loads` | the cache | one process | one process | one process |
| the copies of a near cache | the cache | one process | one process | one process |
| a `Fallback` | its own backend | one process | one process | one process |

## Where entries live

| You have | Take | See |
| --- | --- | --- |
| one process, or tests | `MemoryBackend` | [Memory](backends/memory.md) |
| several processes on one machine and no Redis, or entries that outlive a restart | `SQLiteBackend` | [SQLite](backends/sqlite.md) |
| several processes or machines | `RedisBackend` | [Redis and Valkey](backends/redis.md) |
| Redis Cluster | `RedisBackend` over a `RedisCluster` client | [Redis Cluster](backends/cluster.md) |
| another store | a backend of your own | [Writing your own backend](backends/your-own.md) |

## A near cache, and its bus

A near cache keeps copies in process memory, in front of the shared backend. A read that it
answers costs no round trip, but a copy may be up to `local_ttl` old.

| You have | Take | See |
| --- | --- | --- |
| a key read by most requests, such as settings or a catalog | `NearCacheBackend` in front of Redis | [Near cache](near-cache.md) |
| keys written as often as read, or no tolerance for a copy up to `local_ttl` old | no near cache | |
| a near cache, writes only through pashe | `RedisPubSubBus` | [Telling the other processes](near-cache.md#telling-the-other-processes) |
| a near cache over a Redis Cluster | `RedisPubSubBus`: tracking follows one node | [Writes through pashe](near-cache.md#writes-through-pashe) |
| a near cache, and other services or people write the same keys | `RedisTrackingBus`, on one Redis node of version 6 or later | [Every write, whoever made it](near-cache.md#every-write-whoever-made-it) |
| one process, or copies that may live out `local_ttl` | `NoOpBus`, the default | [How long a copy lives](near-cache.md#how-long-a-copy-lives) |
| sync code over one Redis node, no near cache of pashe | the client-side cache of redis-py | [Redis and Valkey](backends/redis.md) |

## A backend that fails

| You have | Take | See |
| --- | --- | --- |
| a Redis outage shouldn't send every call to the source | `fallback=Fallback(MemoryBackend())` | [A failing backend](fallback.md) |
| a Redis that's down makes every call wait for its timeout | `CircuitBreaker` given to `RedisBackend` | [Skip a backend that is down](fallback.md#skip-a-backend-that-is-down) |
| no Redis outage worth planning for, as with memory or SQLite | neither | |

## How values are stored

| Your functions return | Take | See |
| --- | --- | --- |
| dataclasses, `TypedDict`s, `msgspec.Struct`s | `MsgspecMsgpackCodec`; `MsgspecJsonCodec` when other services read the values | [msgspec](codecs.md#msgspec) |
| pydantic models | `PydanticCodec` | [pydantic](codecs.md#pydantic) |
| plain `dict`s and `list`s | `OrjsonCodec`, or `JsonCodec`, the default, with no extra | [orjson](codecs.md#orjson), [JsonCodec](codecs.md#jsoncodec-the-default) |
| any object, read only by Python | `PickleCodec(secret=...)` | [PickleCodec](codecs.md#picklecodec) |

| Your values are | Take | See |
| --- | --- | --- |
| up to a kilobyte | no compressor, the default | [Small values are stored as they are](compressors.md#small-values-are-stored-as-they-are) |
| kilobytes or more, such as lists and pages | `ZstdCompressor` | [ZstdCompressor](compressors.md#zstdcompressor) |
| kilobytes or more, and no zstd | `GzipCompressor` | [GzipCompressor](compressors.md#gzipcompressor) |

## How fresh a result is

| You have | Take | See |
| --- | --- | --- |
| a result that may be a little old, and calls that must be fast | `Stale(while_revalidate=...)`: calls get the old result at once while one call reloads | [Stale while revalidate](stale.md#stale-while-revalidate) |
| a source that fails now and then | `Stale(if_error=...)`: calls get the old result instead of its errors | [Stale if error](stale.md#stale-if-error) |
| a source that's sometimes slow, and a deadline | `Stale(if_slow=..., slow_after=...)`: calls get the old result while the slow load goes on | [Stale if slow](stale.md#stale-if-slow) |
| a hot key that nobody should ever see stale | `Stampede(revalidate_before=...)`: it reloads in the last seconds of its TTL | [Reload before the TTL](stampedes.md#reload-before-the-ttl) |
| a TTL that depends on the result, such as a token | `ttl=` a function of the result | [TTL from the result](caching/ttl.md#ttl-from-the-result) |
| results not worth keeping, such as an order not done yet | `Store(when=...)` or `Store(slower_than=...)` | [Storing only some results](store.md) |
| a write that changes what a result shows | tags, and `@cache.invalidates` or `invalidate_tags` | [Tags](tags.md) |

## How loads are shared

"Reaches" says where it works over Redis. For a feature that lives in the backend,
[the backend decides](#where-each-feature-works).

| You have | Take | Reaches | See |
| --- | --- | --- | --- |
| calls of the same key at once, in one process | nothing: `Stampede(share_loads=True)` is the default | one process | [Sharing a load within a process](stampedes.md#sharing-a-load-within-a-process) |
| an expensive load, and many processes that miss the key at once | `Stampede(lock_for=...)`: one process loads, the others wait and take its result | every process | [Locking a load across processes](stampedes.md#locking-a-load-across-processes) |
| a source that takes only so many loads at once | `Stampede(max_loads=...)` | one process | [Limiting loads at once](stampedes.md#limiting-loads-at-once) |
| many entries stored at once, such as after a deploy | `Stampede(jitter=0.1)`, so they don't expire together | every process | [Spreading out when entries expire](stampedes.md#spreading-out-when-entries-expire) |
| the same "not found" asked for again and again, such as for unknown ids | `Negative(on=(UserNotFoundError,), ttl=...)` | every process | [Negative caching](negative.md) |

## Locks and rate limits

| You have | Take | Reaches | See |
| --- | --- | --- | --- |
| a block that only one process at a time may run | `with locks.lock(...)` | every process | [Taking a lock](locks.md#taking-a-lock) |
| a job that should skip when another process is already running it | `locks.try_lock(...)` | every process | [Taking a lock if it is free](locks.md#taking-a-lock-if-it-is-free) |
| a function that one process at a time may run, where each call does its own work | `@locks.locked(...)` | every process | [Locking a function](locks.md#locking-a-function) |
| a function that a few may run at once, such as three exports | `@locks.locked(..., holders=3)` | every process | [Several holders](locks.md#several-holders) |
| a cached function whose load only one process should run, while the others take its result | `Stampede(lock_for=...)`, not `@locks.locked` | every process | [Locking a load across processes](stampedes.md#locking-a-load-across-processes) |
| a limit such as "100 a minute", even across window edges | `SlidingWindow`, such as `SlidingWindow.per_minute(100)` | every process | [A sliding window](rate-limits.md#a-sliding-window) |
| a limit that bans for a while once someone goes over it, such as logins | `FixedWindow(..., ban_for=...)` | every process | [A fixed window and a ban](rate-limits.md#a-fixed-window-and-a-ban) |
| a limit for a whole ASGI application | `RateLimitMiddleware` from `pashe.asgi` | every process | [Rate limits for HTTP](rate-limits.md#rate-limits-of-http-requests) |
| a limit for a FastAPI route, per current user | `rate_limit` from `pashe.contrib.fastapi` | every process | [FastAPI](web/fastapi.md) |

## What the cache tells you

| You have | Take | See |
| --- | --- | --- |
| logs only | `LoggingHook`: without it, nobody sees a backend that's down | [Logging](observability/logging.md) |
| Prometheus | `PrometheusMetricsHook` | [Prometheus](observability/prometheus.md) |
| OpenTelemetry | `OtelMetricsHook`, and `OtelSpanEventsHook` for traces | [OpenTelemetry](observability/opentelemetry.md) |
| Sentry | `SentryHook` | [Sentry](observability/sentry.md) |
| HTTP caches in front of you, a CDN or a browser | `CacheHeadersMiddleware` | [HTTP caching headers](web/headers.md) |

For a full setup that covers the common cases, see [Recommended setup](recommended-setup.md).
