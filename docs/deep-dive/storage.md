# What is in Redis

This page shows what a cache keeps in its backend, for when you look at Redis with `redis-cli`.
Every key starts with the cache's `prefix`; the examples use `prefix="shop:"`.

## A cached result

=== "Sync"

    ```python hl_lines="16"
    --8<-- "storage/cached_result_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="16"
    --8<-- "storage/cached_result_async.py:show"
    ```

Called at the moment `1764000000`, `get_user(1)` stores 49 bytes under `shop:user:1`:

```text
03 | 41 da 49 20 8b 00 00 00 | 00 | 96 87 df b8 c0 ce 34 23 | 00 01 | 0b e3 ab 06 f1 d6 9d 90 | {"id":1,"name":"Ada"}
```

| Bytes | Field | Here | What it is |
| ---: | --- | --- | --- |
| 1 | version | `3` | the entry's format; an entry with another version is a miss |
| 8 | `stale_at` | `1764000300.0` | when the result stops being fresh: the moment of the call plus `ttl` |
| 1 | flags | `0` | bit 0: a "not found" kept by `Negative`; bit 1: the payload went through the compressor |
| 8 | `type_fingerprint` | `0x9687dfb8c0ce3423` | a hash of the return type and its fields; when a deploy changes it, the entry is a miss |
| 2 | tags | `1` | how many tag generations follow |
| 8 each | `tag_generations` | `856716400446053776` | each tag's generation when the result was stored |
| the rest | payload | `{"id":1,"name":"Ada"}` | the value, as the codec wrote it and the compressor shrank it |

The numbers are big-endian. The header is 28 bytes here, and the payload follows it unchanged. So
`redis-cli GET` shows a few unreadable bytes, then the value.

The key lives 360 seconds in Redis: 300 for `ttl` plus 60 for the longest `Stale` window. During
the last 60 seconds the key is still there, but `stale_at` has passed. The cache returns the
stale result at once and reloads it in the background.

## The keys of the cache

The cache keeps keys of its own under `prefix + "__"`, so your keys must not start with `"__"`:

| Key | Value | What it's for |
| --- | --- | --- |
| `shop:__tag:users` | `856716400446053776`, as text | the generation of the tag `users`; `invalidate_tags("users")` changes it, and every entry stored with the old one turns into a miss, without scanning keys |
| `shop:__stampede:user:1` | its owner's token | the `Stampede.lock_for` lock while one caller loads `user:1` |
| `shop:__revalidation:user:1` | its owner's token | the lock for the single background revalidation of `user:1` |
| `shop:__lock:report` | its owner's token | a lock taken by `locks.lock("report", ...)`, `try_lock` or `locked`, under the prefix `shop:` |
| `shop:__rate:sliding:100/60.0:ip:1.2.3.4:29400000` | a count, as text | a counter of a `SlidingWindow` of 100 calls per 60 seconds, one per fixed window |
| `shop:__rate:fixed:5/60.0/300.0:login:ada` | a count, as text | the counter of a `FixedWindow` of 5 calls per 60 seconds, with a 300-second ban |

Each of them has a TTL. A lock lives for its `ttl` unless it's extended, and a counter lives for
its window.

## Near caches

By default, `RedisPubSubBus` publishes on the channel `pashe:near-cache`. A message is JSON:

```json
{"keys": ["shop:user:1"]}
```

`{"keys": null}` drops every copy, as after a reconnect. `RedisTrackingBus` publishes nothing:
Redis tells the near caches itself, through `CLIENT TRACKING`.
