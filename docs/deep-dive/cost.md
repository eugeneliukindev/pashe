# What a call costs

What each operation asks of the backend. Over Redis every call below is one round trip: the
conditional ones, such as "delete if equal" and an increment that sets a TTL, are Lua scripts
that run in one. The tests of pashe count these calls, so the tables hold.

## A cached call

| Call | Calls to the backend | Round trips |
| --- | --- | --- |
| a hit, no tags | `GET` | 1 |
| a hit with tags | one `MGET` of the entry and the counters of its tags | 1 |
| a miss, no tags | `GET`, then `SET` after the load | 2 |
| a miss with tags | `MGET`, then `SET`; once per new tag, `SET NX` of its counter | 2, and 1 per new tag |
| a miss under `Stampede(lock_for=...)` | `GET`, `SET NX` of the lock, `GET` once it holds it, `SET`, the release | 5 |
| a stale answer under `Stale(while_revalidate=...)` | `GET`; in the background `SET NX` of the lock, `SET`, the release | 1 for the call, 3 in the background |
| `get`, `set` or `invalidate` of a result | `GET`, `SET` or `DEL` | 1 |
| a call inside `no_cache()` | `MGET` of the counters of its tags, if any, then `SET` | 1 or 2 |

A lookup costs one round trip with or without tags: the counters of the tags come in the same
`MGET` as the entry. A load waiting under `lock_for` checks the lock again after 10 ms, then
waits twice as long each time, up to half a second or a tenth of the TTL of the lock.

On a Redis Cluster the keys of one call may live on different nodes: `MGET` goes as one call
per node at once, and `set_many` of a batch as one pipeline per node.

## Tags and batches

| Call | Round trips |
| --- | --- |
| `invalidate_tags` | 2 per tag: `SET NX` of the counter, then `INCRBY` |
| a batch | one `MGET` of every item and the counters of their tags, then one `SET` per loaded item in one pipeline |

## Locks and rate limits

| Call | Round trips |
| --- | --- |
| `try_lock` | 1: `SET NX` |
| `with locks.lock(...)` | 2: `SET NX`, then the release; one more every third of the TTL while the block runs |
| `try_lock` or `lock` of `holders=N` | 1 `SET NX` for a free place, up to N when the others are taken: it tries them one by one |
| `count` over a `SlidingWindow` | 2: the increment of the current window, the read of the last one; a refused call 1 more, to undo its count |
| `count` over a `FixedWindow` | 2: the increment, then the time left; the call that starts a ban 1 more |

## Near cache

| Call | Round trips |
| --- | --- |
| a read its copy answers | 0 |
| a read it copies | 1 to the shared backend |
| a write | the write, and with `RedisPubSubBus` one `PUBLISH`; `RedisTrackingBus` publishes nothing |

## What an entry takes

An entry is its key, with the prefix of the cache, and a value of 20 bytes of header, 8 bytes
per tag and the payload of the codec, compressed when the compressor finds it smaller. Each tag
is one more key with a counter, shared by every entry of the tag; a lock or a counter of a rate
limit lives only as long as its TTL. What these keys look like: [What is in Redis](storage.md).
