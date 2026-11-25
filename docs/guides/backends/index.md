# Choosing a backend

A backend stores bytes. The cache encodes values with its codec and keeps its own keys, of tags,
locks and rate limits, under `prefix + "__"`.

## Which to take

| You have | Take |
| --- | --- |
| one process, or tests | `MemoryBackend` |
| several processes on one machine and no Redis, or entries that outlive a restart | [`SQLiteBackend`](sqlite.md) |
| several processes or servers | `RedisBackend`, with `fallback=Fallback(MemoryBackend())` so a failing Redis does not reach the source on every call |
| hot keys read by every request | `NearCacheBackend` in front of Redis |
| a near cache, and writes only through pashe | `RedisPubSubBus` |
| a near cache, and writes by other services too | `RedisTrackingBus`: Redis tells about every write |
| sync code and Redis 6 or later | the client-side cache of redis-py, see [`RedisBackend`](redis.md) |

## Every store

| Store | Supported | Why |
| --- | --- | --- |
| Redis, one node, replicas, Sentinel | yes | `RedisBackend`; the tests run against Redis |
| Valkey | yes | `RedisBackend`, the same protocol; the tests run against Valkey 8 and 9 |
| Dragonfly | yes, with `RedisPubSubBus` for a near cache | `RedisBackend`; the tests run against it; some versions lack `CLIENT TRACKING` |
| KeyDB | yes | `RedisBackend`; the tests passed against KeyDB 6.3.4, which CI does not run |
| Garnet | yes, started with `--lua`, and with `RedisPubSubBus` for a near cache | `RedisBackend`; without `--lua` Garnet runs no scripts, which locks and rate limits take; it has no `CLIENT TRACKING`, and an `incr` past 2^63 raises `WrongTypeError` instead of `OverflowError`; the tests passed against Garnet 2.2.14, which CI does not run |
| Redis Cluster | yes, with `RedisPubSubBus` for a near cache | `RedisBackend` over a `RedisCluster` client; the tests run against a cluster of three primaries; `RedisTrackingBus` refuses a cluster, and `AsyncRedisPubSubBus` an async one of redis-py before 8, which has no pub/sub |
| SQLite | yes | `SQLiteBackend`, with `sqlite3` of the standard library; the tests run every scenario over it |
| Memcached | no backend in pashe | a cache needs atomic "delete if equal", the time a key has left and increments that set a TTL; memcached has them only in its meta commands of version 1.6, which the common Python clients do not speak. A backend of your own over them is possible |

---

API reference: [`pashe.backends`](../../reference/backends.md).
