# Redis and Valkey

[`RedisBackend`][pashe.contrib.redis.RedisBackend], the `redis` extra, keeps the entries in Redis or
Valkey.

=== "Sync"

    ```python
    --8<-- "backends/redis_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/redis_async.py"
    ```

Every process that uses the same Redis shares the entries. A backend takes over its client and
closes it; the client must return bytes, so leave `decode_responses` off, and have a
`socket_timeout`, so a Redis that hangs fails a call instead of holding it. [`AsyncRedisBackend`][pashe.contrib.redis.AsyncRedisBackend]
takes a `redis.asyncio.Redis`.

!!! tip "A short timeout lets the fallback answer"

    A client of redis-py 8 or later has a `socket_timeout` of 5 seconds, so the other examples of
    these docs leave it out; before 8 a client has none, and the backend refuses it: pass
    `socket_timeout` there. For a cache, 5 seconds is long: every call waits that long for a Redis
    that hangs before the fallback or a breaker steps in. `socket_timeout=1`, as above, gives up
    sooner.

!!! info "Client-side caching of redis-py"

    For sync code redis-py caches reads itself: give `RedisBackend` a client made with
    `protocol=3, cache_config=CacheConfig()` and reads are answered from memory, invalidated by
    Redis. redis-py has no such cache for async clients; a near cache does that work there.
