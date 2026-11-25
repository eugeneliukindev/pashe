# Redis and Valkey

`RedisBackend` of `pashe.contrib.redis`, the `redis` extra, keeps the entries in Redis or
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
closes it; the client must return bytes, so leave `decode_responses` off. `AsyncRedisBackend`
takes a `redis.asyncio.Redis`.

!!! info "Client-side caching of redis-py"

    For sync code redis-py caches reads itself: give `RedisBackend` a client made with
    `protocol=3, cache_config=CacheConfig()` and reads are answered from memory, invalidated by
    Redis. redis-py has no such cache for async clients; a near cache does that work there.

---

API reference: [`pashe.contrib.redis`](../../reference/contrib/redis.md).
