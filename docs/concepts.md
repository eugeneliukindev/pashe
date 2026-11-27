# Core concepts

This page shows how pashe works, in a few minutes of reading. The [Glossary](glossary.md) gives
each thing one word.

## How a cached call is answered

Each time you call a cached function, pashe reads its entry and decides how to answer:

```mermaid
flowchart TD
    call(["call"]) --> read{"entry?"}
    read -- "fresh" --> hit["answer with it: HIT"]
    read -- "stale, inside a window" --> stale["answer with it, reload in the background"]
    read -- "missing or past every window" --> load["run the function"]
    load -- "result" --> store["store it: MISS"]
    load -- "an error of Stale.if_error or Negative.on" --> old["an old result, or a cached not found"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class hit,stale,old fromCache
    class load,store fromSource
```

A result is **fresh** for its `ttl`. After that it's **stale**. The stale windows of `Stale`
(`while_revalidate`, `if_error` and `if_slow`) let the call return it for a while longer, each in
its own case. Once every window has passed, the entry is gone, and the call loads.

The cache's hooks hear how each call was answered: `on_call` gets a `CacheStatus`, one of `HIT`,
`MISS`, `STALE_WHILE_REVALIDATE`, `STALE_IF_ERROR`, `STALE_IF_SLOW`, `NOT_FOUND` or `FALLBACK`.

## Keys

A call's key is a template over the arguments by name, such as `"user:{user_id}"`. Without a
template, pashe uses the function's qualified name and the `repr` of its arguments. Either way,
the key goes under the cache's `prefix`.

Each part of a key has to read the same in every process. That holds for `str`, `int`, `float`,
`bool`, `None`, `date`, `time`, `datetime`, `UUID`, `Decimal` and enums of those. For any other
value, use a digest, such as `{filters:blake2b}`. [`key`](guides/caching/keys.md) shows how to
build each case.

## Types

A stored result decodes to the function's return annotation. The entry also remembers the
shape of that type: its classes and fields. So when a deploy changes the type, old entries turn
into misses instead of decoding into the wrong shape.

## Tags

`invalidate_tags("users")` turns every result stored with the tag `users` into a miss, no matter
how many there are. It costs two calls to the backend and scans no keys.
[What is in Redis](deep-dive/storage.md#the-keys-of-the-cache) shows how.

## Where each feature works

A feature that lives in the backend works for every process that uses that backend. A feature
that lives in the cache works only in its own process. So the backend decides how far a lock, a
limit or a tag reaches. Over memory, for example, a lock keeps apart the threads and tasks of one
process, but not two machines.

[What to choose](guides/choosing.md#where-each-feature-works) lists where every feature lives.

| In the memory of each process | In Redis, shared by every process |
| --- | --- |
| `Stampede(share_loads=..., max_loads=...)`, the copies of a near cache, the fallback | the entries, the tag counters, the locks of `Stampede(lock_for=...)`, locks, the counters of rate limits |

In the diagrams of these docs, a box shows where something lives. Blue and green boxes are
processes, each with its own memory. The yellow box is Redis, which every process shares.

## Sync and async

Use `Cache` for `def` code over a sync backend, and `AsyncCache` for `async def` code over an
async one. The classes and methods are the same; on the async side you await them. If you
decorate a function of the other side, the decorator refuses it. Both sides behave the same.
