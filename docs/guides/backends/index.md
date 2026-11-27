# Choosing a backend

A backend stores bytes. The cache encodes values with its codec and keeps its own keys, of tags,
locks and rate limits, under `prefix + "__"`.

## Which to take

| You have | Take |
| --- | --- |
| one process, or tests | [`MemoryBackend`][pashe.backends.MemoryBackend] |
| several processes on one machine and no Redis, or entries that outlive a restart | [`SQLiteBackend`](sqlite.md) |
| several processes or machines | [`RedisBackend`][pashe.contrib.redis.RedisBackend], with `fallback=Fallback(MemoryBackend())` so a failing Redis does not reach the source on every call |
| hot keys read by every request | [`NearCacheBackend`][pashe.backends.NearCacheBackend] in front of Redis |
| a near cache, and writes only through pashe | [`RedisPubSubBus`][pashe.contrib.redis.RedisPubSubBus] |
| a near cache, and writes by other services too | [`RedisTrackingBus`][pashe.contrib.redis.RedisTrackingBus]: Redis tells about every write |
| sync code and Redis 6 or later | the client-side cache of redis-py, see [`RedisBackend`](redis.md) |

## Supported servers

| Server | Supported | Notes |
| --- | --- | --- |
| Redis, one node, replicas, Sentinel | yes | `RedisBackend` |
| Valkey | yes | `RedisBackend`, the same protocol; Valkey 8 and 9 |
| Dragonfly | yes, with `RedisPubSubBus` for a near cache | `RedisBackend`; some versions lack `CLIENT TRACKING` |
| KeyDB | yes | `RedisBackend`; KeyDB 6.3.4, not checked with every release |
| Garnet | yes, started with `--lua`, and with `RedisPubSubBus` for a near cache | `RedisBackend`; without `--lua` Garnet runs no scripts, which locks and rate limits take; it has no `CLIENT TRACKING`, and an `incr` past 2^63 raises `WrongTypeError` instead of `OverflowError`; Garnet 2.2.14, not checked with every release |
| Redis Cluster | yes, with `RedisPubSubBus` for a near cache | `RedisBackend` over a `RedisCluster` client; `RedisTrackingBus` refuses a cluster, and `AsyncRedisPubSubBus` an async one of redis-py before 8, which has no pub/sub |
| SQLite | yes | `SQLiteBackend`, with `sqlite3` of the standard library |
| Memcached | no backend in pashe | a cache needs atomic "delete if equal", the time a key has left and increments that set a TTL; memcached has them only in its meta commands of version 1.6, which the common Python clients do not speak. A backend of your own over them is possible |
