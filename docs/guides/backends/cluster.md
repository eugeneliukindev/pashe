# Redis Cluster

[`RedisBackend`][pashe.contrib.redis.RedisBackend] works over a Redis Cluster as well.

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

Pass the same backend a cluster client. You give the client one node, and it finds the others.

A command for one key goes to the node that owns the key's slot. A command for many keys is split
by node: a cached call reads its entry and its tag counters with one `MGET` per node they live on,
and a batch writes with one pipeline per node.

pashe needs no atomicity across keys, so nothing else changes. Tags, batches, locks, rate limits
and a near cache with `RedisPubSubBus` work the same as on one node.
