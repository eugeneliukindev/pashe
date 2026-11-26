# Glossary

The words these docs use, one word for each thing. A word in the API is in code.

## Where things run and live

| Word | What it is |
| --- | --- |
| cache | the object you decorate functions with: `Cache`, or `AsyncCache` for `async def` code |
| backend | where a cache keeps its entries: `MemoryBackend`, `SQLiteBackend`, `RedisBackend`, `NearCacheBackend` |
| server | a Redis server, or Valkey, Dragonfly or Garnet, that a `RedisBackend` talks to; an HTTP server such as gunicorn or uvicorn is a WSGI or ASGI server |
| process | one running copy of your application, such as a worker of gunicorn |
| machine | a computer or a virtual machine that runs processes |
| service | your application as a whole, every process of it on every machine |
| sync, async | the two sides of pashe: `Cache` with `def` functions, or `AsyncCache` with `async def` ones; a function of the side of a cache is `def` for a `Cache`, `async def` for an `AsyncCache` |

A feature that lives in the backend works for every process over that backend; one that lives in
the cache works in its process only: [Where each feature works](guides/choosing.md#where-each-feature-works).

## Calls and what they keep

| Word | What it is |
| --- | --- |
| function | a function you decorate with `@cache(...)`; decorated, a cached function |
| source | what the function asks: a database, an API, a slow computation |
| result | what the function returns |
| key | the name an entry is stored under: the `prefix` of the cache, then the key of the call |
| entry | what the backend keeps for a key: the result and how long it is fresh |
| hit, miss | a call answered from an entry, or one that has to load |
| load | a call of the function on a miss, to get a result and store it |
| reload | a load that replaces a stored result: `refresh()` reloads now, and the `revalidate` options reload in the background |
| fresh, stale | an entry within its `ttl`, or past it and still kept, as `Stale` allows |
| tag | a name of a group of results, which `invalidate_tags` turns into misses at once |
| invalidate | make results misses, so the next calls load: `invalidate`, `invalidate_tags` |

## Around the calls

| Word | What it is |
| --- | --- |
| stampede | many calls that miss one key at once and all ask the source; `Stampede` shares their load |
| near cache | `NearCacheBackend`: copies of hot entries in each process, in front of a shared backend |
| local, shared | the memory of a near cache in this process, and the backend behind it |
| bus | what tells the near caches of every process that keys changed: `RedisPubSubBus`, `RedisTrackingBus` |
| fallback | where a cache keeps what it loads while its backend fails: `Fallback` |
| breaker | what skips a backend that is down for a while: `CircuitBreaker` |
| lock | a lock in the backend that one holder takes at a time, or `holders` of them |
| rate limit | a count of calls per key and window that refuses those over it: `SlidingWindow`, `FixedWindow` |
| hook | what a cache tells how every call was answered and every error it worked around: `Hook` |
| codec, compressor | how a result turns into bytes, and how those bytes shrink: `Codec`, `Compressor` |
