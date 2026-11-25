# Redis Cluster

`RedisBackend` works over a Redis Cluster as well.

=== "Sync"

    ```python
    --8<-- "backends/cluster_sync.py:imports"
    --8<-- "backends/cluster_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "backends/cluster_async.py:imports"
    --8<-- "backends/cluster_async.py:calls"
    ```

The same backend takes a cluster client; the client finds the other nodes from the one it is
given. Every command of one key goes to the node of its slot, and a command of many keys is split
by node: a cached call reads its entry and the counters of its tags with one `MGET` per node they
live on, and a batch writes with one pipeline per node. pashe needs no atomicity across keys, so
nothing else changes: tags, batches, locks, rate limits and a near cache with `RedisPubSubBus`
work as on one node. The tests run every core scenario on a cluster of three primaries.

---

API reference: [`pashe.contrib.redis`](../../reference/contrib/redis.md).
