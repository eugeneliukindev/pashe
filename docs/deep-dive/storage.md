# What is in Redis

What a cache keeps in its backend, for whoever looks at Redis with `redis-cli`. Every key is
under the `prefix` of the cache; the examples use `prefix="shop:"`.

## A cached result

```python
--8<-- "storage/cached_result.py:show"
```

`get_user(1)` at the moment `1764000000` keeps 49 bytes under `shop:user:1`:

```text
03 | 41 da 49 20 8b 00 00 00 | 00 | 96 87 df b8 c0 ce 34 23 | 00 01 | 0b e3 ab 06 f1 d6 9d 90 | {"id":1,"name":"Ada"}
```

| Bytes | Field | Here | What it is |
| ---: | --- | --- | --- |
| 1 | version | `3` | the format of the entry; an entry of another version is a miss |
| 8 | `stale_at` | `1764000300.0` | when the result stops being fresh: the moment of the call plus `ttl` |
| 1 | flags | `0` | bit 0: a kept "not found" of `Negative`; bit 1: the payload went through the compressor |
| 8 | `type_fingerprint` | `0x9687dfb8c0ce3423` | a hash of the return type and its fields: after a deploy changes it, the entry is a miss |
| 2 | tags | `1` | how many generations of tags follow |
| 8 each | `tag_generations` | `856716400446053776` | the generation of each tag when the result was stored |
| the rest | payload | `{"id":1,"name":"Ada"}` | the value, as the codec wrote it and the compressor shrank it |

The numbers are big-endian. The header is 28 bytes here; the payload follows it as it is, so
`redis-cli GET` shows a few unreadable bytes, then the value.

The key lives 360 seconds in Redis: the 300 of `ttl` plus the 60 of the longest `Stale` window.
For the last 60 the key is still there, but `stale_at` is past: the cache answers with it at
once and reloads it in the background.

## The keys of the cache

The cache keeps keys of its own under `prefix + "__"`, so keys of yours must not start with
`"__"`:

| Key | Value | What it is for |
| --- | --- | --- |
| `shop:__tag:users` | `856716400446053776`, as text | the generation of the tag `users`: `invalidate_tags("users")` changes it, and every entry stored with the old one is a miss, with no scan of keys |
| `shop:__stampede:user:1` | the token of its owner | the lock of `Stampede.lock_for` while one caller loads `user:1` |
| `shop:__revalidation:user:1` | the token of its owner | the lock of the one revalidation of `user:1` in the background |
| `shop:__lock:report` | the token of its owner | a lock of `locks.lock("report", ...)`, `try_lock` or `locked`, over the prefix `shop:` |
| `shop:__rate:sliding:100/60.0:ip:1.2.3.4:29400000` | a count, as text | a counter of a `SlidingWindow` of 100 calls per 60 seconds, one per fixed window |
| `shop:__rate:fixed:5/60.0/300.0:login:ada` | a count, as text | the counter of a `FixedWindow` of 5 calls per 60 seconds with a ban of 300 |

Each of them has a TTL: a lock lives its `ttl` unless it is extended, a counter its window.

## Near caches

`RedisPubSubBus` publishes on the channel `pashe:near-cache` by default; a message is JSON:

```json
{"keys": ["shop:user:1"]}
```

`{"keys": null}` drops every copy, as after a reconnect. `RedisTrackingBus` publishes nothing:
Redis tells the near caches itself, through `CLIENT TRACKING`.
