# Memcached

[`MemcachedBackend`][pashe.backends.MemcachedBackend] keeps entries in memcached 1.6.13 or later.
pashe speaks memcached's protocol itself, so you need no extra and no client library.

=== "Sync"

    ```python
    --8<-- "backends/memcached_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/memcached_async.py"
    ```

Every process that uses the same memcached shares the entries, tags, locks and rate limits. The
backend opens its connections at the first call and closes them when you close the cache. A call
waits up to [`timeout`][pashe.backends.MemcachedBackend(timeout)], 1 second by default, then
raises `BackendError`, so a fallback or a breaker can step in.

## What memcached does differently

pashe needs a few things memcached's classic commands can't do: delete a key only if it still holds
a value, read how long a key has left, and count below zero. memcached's meta commands give
the first two, and pashe counts on its own under a CAS token. That's why older memcached versions
don't work: before 1.6.13, a delete under a CAS token always fails.

memcached keeps TTLs in whole seconds, so pashe rounds a TTL up: `ttl=0.5` lives for 1 second. A
key longer than memcached takes, 186 bytes, goes in as a digest of itself, so any key works.

!!! warning "memcached drops entries when its memory runs out"

    When memcached is full, it drops the least recently used entries. That's fine for a cached
    result: the next call loads it again. But it drops locks and rate limit counts too. A lock that
    disappears lets a second holder in, and a count that disappears lets more calls through. Give
    memcached enough memory for them, or keep locks and rate limits on Redis.

memcached has no pub/sub, so it can't carry the bus of a [near cache](../near-cache.md). You can
still put a near cache in front of memcached, without a bus: after another process writes a key,
your copy of it is returned for up to [`local_ttl`][pashe.backends.NearCacheBackend(local_ttl)].
