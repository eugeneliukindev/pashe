# Migrating from cashews and aiocache

Coming from cashews or aiocache? This page maps what you use there to what pashe calls it, and
lists the differences that bite during a move. The tables follow cashews 7.6.0 and aiocache
0.12.3, the versions [the comparison](../deep-dive/comparison.md) covers.

## From cashews

| In cashews | In pashe | Guide |
| --- | --- | --- |
| `cache.setup("mem://")`, `"redis://..."` | [`Cache`][pashe.Cache] over a [`MemoryBackend`][pashe.backends.MemoryBackend] or a [`RedisBackend`][pashe.contrib.redis.RedisBackend] | [Choosing a backend](backends/index.md) |
| `cache.setup("disk://")` | [`SQLiteBackend`][pashe.backends.SQLiteBackend], the closest: it's on disk too, but it isn't diskcache | [SQLite](backends/sqlite.md) |
| `@cache(ttl=...)` | [`@cache(ttl=...)`][pashe.Cache.__call__] | [Caching a function](caching/decorator.md) |
| `key="user:{user_id}"` | [`key`][pashe.Cache.__call__(key)], the same braces | [Keys](caching/keys.md) |
| `prefix=` on each decorator | [`prefix`][pashe.Cache(prefix)], once for the whole cache | [Keys](caching/keys.md) |
| `@cache.early(early_ttl=...)` | [`revalidate_before`][pashe.options.Stampede(revalidate_before)] | [Reload before the TTL](stampedes.md#reload-before-the-ttl) |
| `@cache.soft(soft_ttl=...)`, `@cache.failover(exceptions=...)` | [`if_error`][pashe.options.Stale(if_error)] with [`if_error_on`][pashe.options.Stale(if_error_on)] | [Stale if error](stale.md#stale-if-error) |
| `@cache(lock=True)` | [`lock_for`][pashe.options.Stampede(lock_for)] | [Locking a load across processes](stampedes.md#locking-a-load-across-processes) |
| concurrent calls of one key share a task | [`share_loads`][pashe.options.Stampede(share_loads)], on by default | [Sharing a load within a process](stampedes.md#sharing-a-load-within-a-process) |
| `@cache.locked(...)` | [`Locks.lock`][pashe.Locks.lock] | [Locks](locks.md) |
| `tags=[...]` and `cache.delete_tags(...)` | [`tags`][pashe.Cache.__call__(tags)] and [`invalidate_tags`][pashe.Cache.invalidate_tags] | [Tags and invalidation](tags.md) |
| `@cache.invalidate("key template")` | [`@cache.invalidates(tags=[...])`][pashe.Cache.invalidates]: it drops tags, not keys | [Invalidating on writes](tags.md#invalidating-on-writes) |
| `@cache.rate_limit(limit, period, ttl)` | [`RateLimiter`][pashe.RateLimiter] with a [`FixedWindow`][pashe.ratelimit.FixedWindow]; cashews' `ttl` ban is `ban_for` | [A fixed window and a ban](rate-limits.md#a-fixed-window-and-a-ban) |
| `@cache.slice_rate_limit(limit, period)` | [`SlidingWindow`][pashe.ratelimit.SlidingWindow] | [A sliding window](rate-limits.md#a-sliding-window) |
| `condition=` | [`when`][pashe.options.Store(when)] | [Storing only some results](store.md) |
| `time_condition=` | [`slower_than`][pashe.options.Store(slower_than)] | [A load that was fast](store.md#a-load-that-was-fast) |
| `pickle_type=` | a [`codec`][pashe.Cache(codec)], such as [`PickleCodec`][pashe.codecs.PickleCodec] | [Codecs](codecs.md) |
| `"redis://...?client_side=true"` | [`NearCacheBackend`][pashe.backends.NearCacheBackend] with a [`RedisTrackingBus`][pashe.contrib.redis.RedisTrackingBus] | [Near cache](near-cache.md) |
| `cache.get(key)`, `cache.set(key, ...)`, `cache.delete(key)` | `get`, `set` and `invalidate` of the cached function, with its arguments; or [`@cache.value`][pashe.Cache.value] for data no function loads | [Reading and writing a result](caching/decorator.md#reading-and-writing-a-result) |

Two cashews decorators have no counterpart. `@cache.hit` reloads after a number of hits, and
pashe only counts time. `@cache.circuit_breaker` wraps your function, while pashe's
[`CircuitBreaker`][pashe.backends.CircuitBreaker] guards the backend. For your function, put a
breaker from another library under the cache, as [Stale if error](stale.md#stale-if-error)
shows.

## From aiocache

| In aiocache | In pashe | Guide |
| --- | --- | --- |
| `SimpleMemoryCache`, `RedisCache`, `MemcachedCache` | [`MemoryBackend`][pashe.backends.MemoryBackend], [`RedisBackend`][pashe.contrib.redis.RedisBackend], [`MemcachedBackend`][pashe.backends.MemcachedBackend] | [Choosing a backend](backends/index.md) |
| `@cached(ttl=...)` | [`@cache(ttl=...)`][pashe.Cache.__call__] | [Caching a function](caching/decorator.md) |
| `key=` or `key_builder=` | [`key`][pashe.Cache.__call__(key)], a template over the arguments | [Keys](caching/keys.md) |
| `namespace=` | [`prefix`][pashe.Cache(prefix)] | [Keys](caching/keys.md) |
| `noself=True` | nothing to do: `self` and `cls` stay out of the default key | [Caching a function](caching/decorator.md) |
| `@cached_stampede(lease=...)` | [`lock_for`][pashe.options.Stampede(lock_for)] | [Locking a load across processes](stampedes.md#locking-a-load-across-processes) |
| `@multi_cached(keys_from_attr=...)` | [`@cache.batch(...)`][pashe.Cache.batch] | [Batches](caching/batches.md) |
| `skip_cache_func=` | [`when`][pashe.options.Store(when)], with the meaning flipped: it says what to store | [Storing only some results](store.md) |
| `serializer=` | a [`codec`][pashe.Cache(codec)] | [Codecs](codecs.md) |
| `cache.get`, `cache.set`, `cache.delete` | `get`, `set` and `invalidate` of the cached function; or [`@cache.value`][pashe.Cache.value] | [Reading and writing a result](caching/decorator.md#reading-and-writing-a-result) |

aiocache has no tags, stale results, near cache or rate limits. pashe adds them when you need
them: [Tags and invalidation](tags.md), [Stale results](stale.md), [Near cache](near-cache.md),
[Rate limits](rate-limits.md).

## What works differently

**Your cache starts empty.** pashe builds its own keys and stores its own entry format, so it
can't read what cashews or aiocache wrote. Deploy it with an empty cache, or with a new
`prefix`, and expect a burst of misses at first.

**`ttl` is required.** aiocache keeps a result forever when you leave `ttl` out. pashe makes you
choose one on every decorator: [TTL](caching/ttl.md).

**The return annotation decides the type.** cashews pickles values in Redis by default, and
aiocache's `RedisCache` uses JSON. pashe's default [`JsonCodec`][pashe.codecs.JsonCodec] rebuilds
the type your function's return annotation names, and refuses a type it can't rebuild when you
decorate the function. Pick a codec that fits your types: [Codecs](codecs.md).

**A `None` result is a hit.** aiocache reads a stored `None` as a miss, so a function that
returns `None` reaches its source on every call. pashe stores it like any other result. For
"there's no such thing", raise an error and keep it with [Negative caching](negative.md).

**Sync code works too.** cashews and aiocache are async only. pashe has a [`Cache`][pashe.Cache]
for `def` functions and an [`AsyncCache`][pashe.AsyncCache] for `async def` ones, with the same
options.
