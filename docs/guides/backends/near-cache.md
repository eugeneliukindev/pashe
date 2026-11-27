# Near cache

`NearCacheBackend`, a near cache, keeps copies of hot keys in the memory of each process, in front of a shared
backend such as Redis. A read of a copy does not leave the process: hot keys do not load one
Redis node, and reads go on for a while when Redis is slow.

!!! info "Where it works"

    The copies live in each process; the bus tells every process over the shared backend to drop
    them. See [Where each feature works](../choosing.md#where-each-feature-works).

=== "Sync"

    ```python
    --8<-- "backends/near_cache_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "backends/near_cache_async.py:show"
    ```

```mermaid
flowchart LR
    subgraph p1["Process 1"]
        request(["a call"]) --> local1["local copy, 5 s"]
    end
    subgraph p2["Process 2"]
        local2["local copy"]
    end
    subgraph shared["Redis: every process"]
        redis[("entries")]
    end
    source["the function"]
    local1 -- "miss" --> redis
    redis -- "miss" --> source
    redis -. "the bus drops it" .-> local2
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class local1,local2,redis fromCache
    class source fromSource
    style p1 fill:#2b5b8424,stroke:#2b5b84
    style p2 fill:#00968824,stroke:#009688
    style shared fill:#f7b5002e,stroke:#c98f00
```

API reference: [`NearCacheBackend`](../../reference/backends.md#pashe.backends.NearCacheBackend).

## How it reads and writes

1. A read looks in the local memory first. A copy answers at once.
2. A key without a copy is read from the shared backend, and the value is copied to local memory
   for `local_ttl` seconds, 5 by default. `MemoryBackend(max_entries=...)` bounds the copies.
3. A write goes to the shared backend and drops the local copy of the key, so this process reads
   the new value next.
4. Other processes still hold their copies. Without a bus each answers with its copy for up to
   `local_ttl`: that is how stale a near cache may be. A bus tells them at once.

`hooks=` takes the hooks of the cache, such as the metrics of `pashe.contrib.opentelemetry`: a
near cache tells them how many keys its copies answered, with `on_near_read`, and when it dropped
every copy, with `on_near_flush`. A Redis bus takes `hooks=` too: it tells `on_error` of an
error while it listens other than a lost connection, such as of a hook, and listens again. See
[Metrics and logs](../observability/hooks.md).

## Telling the other processes

A bus carries "these keys changed" between the near caches of every process; only the names of
keys travel, never values. A near cache starts listening to its bus on its first read, and a
process that hears of a key drops its copy: its next read goes to the shared backend.

```mermaid
sequenceDiagram
    box rgba(43,91,132,0.14) Process 1
        participant A as pashe
    end
    participant O as Another service
    box rgba(247,181,0,0.18) Redis: every process
        participant R as Redis
    end
    box rgba(0,150,136,0.14) Process 2
        participant B as Near cache
    end
    A->>R: SET user:1
    A->>R: PUBLISH user:1
    R-->>B: RedisPubSubBus: drop user:1
    O->>R: SET user:2
    R-->>B: RedisTrackingBus: drop user:2, as Redis saw the write
```

| Bus | How it learns of a change | Sees writes of | Needs |
| --- | --- | --- | --- |
| `RedisPubSubBus` | the writer publishes the keys it changed on a channel | pashe only | any Redis, Valkey, a Redis Cluster |
| `RedisTrackingBus` | Redis tells, with `CLIENT TRACKING` in broadcasting mode | anyone: pashe, other services, `redis-cli` | Redis or Valkey 6 or later, one node |

=== "RedisPubSubBus"

    === "Sync"

        ```python
        --8<-- "backends/pubsub_bus_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "backends/pubsub_bus_async.py:show"
        ```

    The near cache that writes publishes the changed keys on a channel, `pashe:near-cache` by
    default; every process subscribed to it drops its copies. Give every process of one cache the
    same channel, and two caches that must not hear each other different ones. Writes made past
    pashe, by another service or by hand, are not published: those copies live out `local_ttl`.

    Near caches may share a bus and its client.

    API reference: [`RedisPubSubBus`](../../reference/contrib/redis.md#pashe.contrib.redis.RedisPubSubBus).

=== "RedisTrackingBus"

    === "Sync"

        ```python
        --8<-- "backends/tracking_bus_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "backends/tracking_bus_async.py:show"
        ```

    Redis itself tells about every write under a prefix, whoever made it, so pashe publishes
    nothing. Give it the prefix of the cache, such as `prefix="app:"`: without one every process
    hears of every write to the whole Redis. Tracking in broadcasting mode costs the server no
    memory. The bus listens on a connection of its own; on a Redis Cluster a node tracks only its
    own keys, so take `RedisPubSubBus` there.

    API reference: [`RedisTrackingBus`](../../reference/contrib/redis.md#pashe.contrib.redis.RedisTrackingBus).

### When messages are lost

A message sent while a process is disconnected never reaches it. So whenever a bus cannot be
sure it heard everything, as after an error of its connection, the near cache drops all its
copies, and listens again by itself. A publish that failed is not raised, as the write itself
succeeded; the other processes then drop their copies within `local_ttl` at the latest.

!!! note

    `RedisTrackingBus` needs Redis or Valkey 6 or later; a clone of Redis without
    `CLIENT TRACKING`, such as some versions of Dragonfly, takes `RedisPubSubBus`.

### Writing your own bus

Subclass `InvalidationBus`, or `AsyncInvalidationBus`, from `pashe.invalidation`, for another
transport such as NATS or Kafka. `publish(keys)` tells the other processes that keys changed;
`None` means every key. `listen(on_invalidate)` calls `on_invalidate`, an `InvalidationHandler`, or
an `AsyncInvalidationHandler` on the async side, with the keys others publish, until the function
it returns is called. A near cache without `bus=` has `NoOpBus`, `AsyncNoOpBus` on the async side,
which tells no one.

API reference: [`InvalidationBus`](../../reference/invalidation.md#pashe.invalidation.InvalidationBus).

---

API reference: [`pashe.backends`](../../reference/backends.md), [`pashe.invalidation`](../../reference/invalidation.md), [`pashe.contrib.redis`](../../reference/contrib/redis.md).
