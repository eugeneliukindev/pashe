# Options

Everything a cache and its decorators take, on one page. `AsyncCache` takes the same, with
`AsyncBackend` in place of `Backend`. Every option but the backend is keyword-only. A duration
is seconds, or a `timedelta`; `0` turns an option off.

## `Cache(...)`

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `backend` | `Backend` | required | where entries live: [memory, Redis or a near cache](../guides/backends/index.md) |
| `prefix` | `str` | `""` | goes in front of every key, so services can share a backend |
| `codec` | `Codec` | `JsonCodec()` | the format of stored values, see [codecs](../guides/values/codecs.md) |
| `hooks` | `list[Hook] | tuple[Hook, ...]` | `()` | what the cache tells about itself, for metrics and logs: [below](#hook) |
| `fallback` | `Fallback | None` | `None` | keeps results while the backend fails: [below](#fallback) |
| `compressor` | `Compressor` | `NoOpCompressor()` | shrinks stored values from its `min_size`; `NoOpCompressor` stores them as they are, see [compressors](../guides/values/compressors.md) |
| `key_secret` | `str | bytes | None` | `None` | the secret of `{name:hmac}` in keys and tags, at least 16 bytes |
| `clock` | `Callable[[], float]` | `time.time` | wall-clock seconds, for [tests](../guides/testing.md) |

## `Fallback`

Where a cache keeps the results it loads while its backend fails, and for how long, from
`pashe.options`. See [`Fallback`](../guides/failures/failing-backend.md).

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `backend` | `Backend` | required | where the results are kept, usually a memory backend of the side of the cache |
| `ttl` | `float | int | timedelta` | `30` | the longest a result stays there, as no invalidation reaches it; never past its own TTL |

## `Hook`

What a cache tells about itself, from `pashe.hooks`: a subclass overrides the methods it needs,
the others do nothing, and the cache calls its hooks in the order of the list.

| Method | Gets | When |
| --- | --- | --- |
| `on_call` | an [`Outcome`](hooks.md#pashe.hooks.Outcome): the function, the key, how it was answered, the seconds of the load, how long the result stays fresh | every cached call, and every item of a batch |
| `on_error` | a [`Failure`](hooks.md#pashe.hooks.Failure): the `Operation`, the key and the [error](errors.md) | every error the cache works around instead of raising it |
| `on_rate_limit` | a [`RateLimitDecision`](hooks.md#pashe.hooks.RateLimitDecision): the key, and whether the call went through | every call a rate limit counted |
| `on_near_read` | a [`NearRead`](hooks.md#pashe.hooks.NearRead): the keys its copies answered, and those read from the shared backend | every read of a near cache given the hook |
| `on_near_flush` | nothing | a near cache given the hook dropped every copy |
| `on_circuit` | a [`Circuit`](hooks.md#pashe.hooks.Circuit): whether it opened or closed | the `CircuitBreaker` of a backend, given the hook, opened or closed |

## `@cache(...)`

`R` in the type of `ttl` is the type the function returns.

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `ttl` | `float | int | timedelta | Callable[[R], float | int | timedelta]` | required | how long a result is fresh: seconds, a `timedelta`, or a function that gets the result and returns one, such as `lambda token: token.expires_in - 60` |
| `key` | `str | None` | `None` | a `str.format` template over the arguments by name; `None` is the name of the function and the `repr` of its arguments |
| `tags` | `list[str] | tuple[str, ...]` | `()` | templates like `key`; `invalidate_tags` of any of them makes the result a miss; not a `str`, it would split into letters |
| `stale` | `Stale` | `Stale()` | how long after the TTL a stale result still answers, and in which cases: [below](#stale) |
| `stampede` | `Stampede` | `Stampede()` | how the loads of a key are shared and spread: [below](#stampede) |
| `negative` | `Negative` | `Negative()` | loader errors kept as the answer "no such data": [below](#negative); `Negative()` keeps none |
| `store` | `Store` | `Store()` | which loaded results are stored: [below](#store) |

The groups are in `pashe.options`; one left out takes its defaults. Every option at once:

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_options_async.py:show"
    ```

A group checks its options when it is made: options that cannot work together, such as
`Stampede(revalidate_before=60)` with `ttl=60`, raise `InvalidOptionsError` at once, where the group
is written.

## `Stale`

How long after its TTL a stale result still answers, and in which case; `0` turns a window off.
The windows are explained in [Stale results and failures](../guides/failures/stale.md).

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `while_revalidate` | `float | int | timedelta` | `0` | a stale result answers at once while one caller reloads it in the background |
| `if_error` | `float | int | timedelta | IfError` | `0` | a stale result answers a loader error; a duration answers every `Exception`, `IfError` names the errors |
| `if_slow` | `IfSlow | None` | `None` | a stale result answers a loader slower than `IfSlow.after`; the load goes on in the background |

`IfError(window, *, on=(Exception,))` is the window, and the loader errors it answers, such as
`IfError(600, on=(ConnectionError, TimeoutError))`. `IfSlow(window, *, after)` is the window, and
how long a call waits for the loader, more than 0: `IfSlow(300, after=0.2)`.

## `Stampede`

How the loads of a key are shared and spread, so the source is not asked by every caller at
once; see [`Stampede`](../guides/failures/stampedes.md).

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `revalidate_before` | `float | int | timedelta` | `0` | in the last seconds of the TTL a fresh result answers at once while one caller reloads it in the background; shorter than a fixed `ttl` |
| `lock_for` | `float | int | timedelta` | `0` | a missing key loads under a lock of every process, held at most this long; `0` is off |
| `jitter` | `float | int` | `0` | spreads TTLs by up to this share, so entries stored together do not expire together: `0.1` is +-10% |
| `max_concurrent_loads` | `int` | `0` | how many loads may run at once in a process; `0` is no limit |
| `single_flight` | `bool` | `True` | concurrent calls of a key in a process share one lookup and one load |

## `Negative`

Negative caching: loader errors that mean "there is no such data", kept as the answer, so the
source is not asked again for what it does not have; see [`Negative`](../guides/caching/what-is-stored.md#negative-caching).

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `on` | `tuple[type[Exception], ...]` | `()` | the loader errors that mean "not found", such as `(UserNotFoundError,)`; cached as `NotFoundError` |
| `ttl` | `float | int | timedelta` | `0` | how long a "not found" is kept; positive once `on` names an error |

## `Store`

Which loaded results are stored; by default every one. See
[`Store`](../guides/caching/what-is-stored.md#storing-only-some-results).

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `when` | `Callable[[R], bool] | None` | `None` | stores a result only if it returns true; `None` stores every result |
| `slower_than` | `float | int | timedelta` | `0` | stores only results whose load took at least this many seconds |

## `@cache.batch(...)`

A function of a list of items that returns a dict of them, cached per item; see
[batches](../guides/caching/batches.md).

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `ttl` | `float | int | timedelta | Callable[[R], float | int | timedelta]` | required | as in `@cache(...)` |
| `key` | `str | None` | `None` | a template over the item, such as `"user:{}"`; `None` is the name of the function and the `repr` of the item |
| `stampede` | `Stampede` | `Stampede()` | its `jitter`, and `max_concurrent_loads`: how many batches may load at once in a process; a batch shares no loads, so `lock_for` is refused |
| `store` | `Store` | `Store()` | as in `@cache(...)`, per item; `slower_than` is of the load of the whole batch |
