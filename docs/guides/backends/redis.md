# Redis and Valkey

[`RedisBackend`][pashe.contrib.redis.RedisBackend], from the `redis` extra, keeps entries in Redis
or Valkey.

=== "Sync"

    ```python
    --8<-- "backends/redis_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/redis_async.py"
    ```

Every process that uses the same Redis shares the entries. The backend takes over its client and
closes it when it's done.

The client has to return bytes, so leave `decode_responses` off. It also needs a
`socket_timeout`, so a Redis that hangs fails the call instead of holding it.
[`AsyncRedisBackend`][pashe.contrib.redis.AsyncRedisBackend] takes a `redis.asyncio.Redis`.

!!! tip "A short timeout lets the fallback answer"

    A redis-py 8 client has a `socket_timeout` of 5 seconds by default, so the other examples in
    these docs leave it out. Before redis-py 8 a client has none, and the backend refuses it, so
    pass `socket_timeout` there. For a cache, 5 seconds is long: every call waits that long for a
    Redis that hangs before the fallback or a breaker steps in. `socket_timeout=1`, as above,
    gives up sooner.

!!! info "Client-side caching of redis-py"

    In sync code, redis-py can cache reads itself. Give `RedisBackend` a client made with
    `protocol=3, cache_config=CacheConfig()`, and reads come from memory, with Redis telling the
    client when to drop them. redis-py has no such cache for async clients: there, a near cache
    does the job.
