# What a call costs

Here's what each operation asks of the backend. Over Redis, every call below takes one round
trip. The conditional ones, such as "delete if equal" and an increment that sets a TTL, are Lua
scripts that run in one round trip. pashe's tests count these calls, so the tables stay true.

## A cached call

| Call | Calls to the backend | Round trips |
| --- | --- | --- |
| a hit, no tags | `GET` | 1 |
| a hit with tags | one `MGET` of the entry and its tags' counters | 1 |
| a miss, no tags | `GET`, then `SET` after the load | 2 |
| a miss with tags | `MGET`, then `SET`; for each new tag, a `SET NX` of its counter | 2, and 1 per new tag |
| a miss under `Stampede(lock_for=...)` | `GET`, `SET NX` of the lock, `GET` once it holds the lock, `SET`, the release | 5 |
| a stale result under `Stale(while_revalidate=...)` | `GET`; in the background, `SET NX` of the lock, `SET`, the release | 1 for the call, 3 in the background |
| `get`, `set` or `invalidate` of a result | `GET`, `SET` or `DEL` | 1 |
| a call inside `no_cache()` | `MGET` of its tags' counters, if it has tags, then `SET` | 1 or 2 |

A lookup costs one round trip, with or without tags: the tags' counters come in the same `MGET`
as the entry.

A load that waits under `lock_for` checks the lock again after 10 ms. Then it waits twice as long
each time, up to half a second or a tenth of the lock's TTL.

On a Redis Cluster, the keys of one call can live on different nodes. `MGET` then goes out as one
call per node, all at once, and a batch's `set_many` as one pipeline per node.

## Tags and batches

| Call | Round trips |
| --- | --- |
| `invalidate_tags` | 2 per tag: `SET NX` of the counter, then `INCRBY` |
| a batch | one `MGET` of every item and their tags' counters, then one `SET` per loaded item, in one pipeline |

## Locks and rate limits

| Call | Round trips |
| --- | --- |
| `try_lock` | 1: `SET NX` |
| `with locks.lock(...)` | 2: `SET NX`, then the release; one more every third of the TTL while the block runs |
| `try_lock` or `lock` with `holders=N` | 1 `SET NX` when a place is free, up to N when the others are taken: it tries them one by one |
| `count` over a `SlidingWindow` | 2: the increment of the current window and the read of the last one; a refused call takes 1 more, to undo its count |
| `count` over a `FixedWindow` | 2: the increment, then the time left; the call that starts a ban takes 1 more |

## Near cache

| Call | Round trips |
| --- | --- |
| a read that its copy answers | 0 |
| a read that makes a copy | 1 to the shared backend |
| a write | the write, plus one `PUBLISH` with `RedisPubSubBus`; `RedisTrackingBus` publishes nothing |

## What an entry takes

An entry is its key, with the cache's prefix, plus a value. The value holds a 20-byte header,
8 bytes per tag and the codec's payload. The payload is compressed when the compressor makes it
smaller.

Each tag is one more key with a counter, shared by every entry with that tag. A lock or a rate
limit counter lives only as long as its TTL. To see what these keys look like, read
[What is in Redis](storage.md).
