# Glossary

These are the words the docs use, one word for each thing. A word that's part of the API is in
code.

## Where things run and live

| Word | What it is |
| --- | --- |
| cache | the object you decorate functions with: `Cache`, or `AsyncCache` for `async def` code |
| backend | where a cache keeps its entries: `MemoryBackend`, `SQLiteBackend`, `RedisBackend`, `NearCacheBackend` |
| server | a Redis server, or Valkey, Dragonfly or Garnet, that a `RedisBackend` talks to, or a memcached that a `MemcachedBackend` talks to; an HTTP server such as gunicorn or uvicorn is a WSGI or ASGI server |
| process | one running copy of your application, such as a worker of gunicorn |
| machine | a computer or a virtual machine that runs processes |
| service | your application as a whole: all its processes on all machines |
| sync, async | the two sides of pashe: `Cache` with `def` functions, or `AsyncCache` with `async def` ones; a function on a cache's side is `def` for a `Cache` and `async def` for an `AsyncCache` |

A feature that lives in the backend works for every process that uses that backend. A feature
that lives in the cache works only in its own process. See
[Where each feature works](guides/choosing.md#where-each-feature-works).

## Calls and what they keep

| Word | What it is |
| --- | --- |
| function | a function you decorate with `@cache(...)`; once decorated, it's a cached function |
| source | what the function asks: a database, an API, a slow computation |
| result | what the function returns |
| key | the name an entry is stored under: the cache's `prefix`, then the call's key |
| prefix | the start of every key a cache writes: `Cache(prefix="app:")` |
| template | a key or a tag with argument names in braces, such as `"user:{user_id}"`; each call fills them in |
| digest | a short hash of an argument, such as `{filters:blake2b}`, for a value that has no stable text or shouldn't show up in a key |
| entry | what the backend keeps for a key: the result, and how long it's fresh |
| hit, miss | a call answered from an entry, or one that has to load |
| load | running the function on a miss, to get a result and store it |
| reload | a load that replaces a stored result: `refresh()` reloads now, and the `revalidate` options reload in the background |
| fresh, stale | an entry within its `ttl`, or past it and still kept, as `Stale` allows |
| expire | what an entry does when its `ttl` ends: it turns stale, or a miss when no window of `Stale` keeps it |
| stale window | how long past its `ttl` a stale result is still returned, one for each case of `Stale` |
| tag | a name for a group of results; `invalidate_tags` turns them all into misses at once |
| invalidate | make results misses, so the next calls load: `invalidate`, `invalidate_tags` |
| value | what `@cache.value` keeps: data your code writes and no function loads; what a function returns is a result |
| not found | an error of your function that means "there's no such data", kept as an entry by `Negative`: the next calls raise `NotFoundError` without asking the source |

## Around the calls

| Word | What it is |
| --- | --- |
| stampede | many calls that miss one key at once and all ask the source; `Stampede` shares their load |
| near cache | `NearCacheBackend`: copies of hot entries in each process, in front of a shared backend |
| copy | an entry a near cache keeps in the memory of one process; it's dropped when the bus says the key changed |
| local, shared | the memory of a near cache in this process, and the backend behind it |
| bus | what tells the near cache in every process that keys changed: `RedisPubSubBus`, `RedisTrackingBus` |
| fallback | where a cache keeps what it loads while its backend fails: `Fallback` |
| breaker | what skips a backend that's down, for a while: `CircuitBreaker` |
| lock | a lock in the backend that one holder takes at a time, or `holders` of them: `Locks` takes them |
| holder | whoever has taken a lock; a lock lets in one holder at a time, or `holders` of them |
| rate limit | a count of calls per key and window that refuses those over it: `SlidingWindow`, `FixedWindow`, counted by `RateLimiter` |
| window | the span of time a rate limit counts calls in, such as a minute; not a stale window |
| hook | what a cache tells how it answered each call, and each error it worked around: `Hook` |
| codec, compressor | how a result turns into bytes, and how those bytes shrink: `Codec`, `Compressor` |
