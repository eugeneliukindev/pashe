# Stale results

A stored result past its TTL is stale. [`Stale`][pashe.options.Stale], from `pashe.options`,
keeps it answering for a while longer, each window in its own case: while it is
[reloaded](#stale-while-revalidate), when the source [fails](#stale-if-error) or is
[slow](#stale-if-slow). Every window is off until you set it, and the backend keeps a result long
enough for each one, so a stale result answers in every process:
[How long the backend keeps a result](#how-long-the-backend-keeps-a-result).

## Stale while revalidate

A call right after the TTL would wait for the reload. Within
[`while_revalidate`][pashe.options.Stale(while_revalidate)] the stale result answers it at once,
and one caller reloads it in the background.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "staleness/while_revalidate_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "staleness/while_revalidate_async.py:show"
    ```

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 60" data-start="0"><b>HIT</b><br>fresh</div>
<div class="pashe-timeline__stale" style="flex: 30" data-start="60 s"><b>STALE_WHILE_REVALIDATE</b><br>at once, a reload in the background</div>
<div class="pashe-timeline__source" data-start="90 s"><b>MISS</b><br>the call waits for the load</div>
</div>

Callers never wait for the source while the window lasts. To reload before the result goes stale,
see [Reload before the TTL](stampedes.md#reload-before-the-ttl).

## Stale if error

When the source fails, the call would raise. Within [`if_error`][pashe.options.Stale(if_error)]
the stale result answers the errors of [`if_error_on`][pashe.options.Stale(if_error_on)] instead,
and the error goes to `on_error`.

=== "Sync"

    ```python hl_lines="15"
    --8<-- "staleness/if_error_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="15"
    --8<-- "staleness/if_error_async.py:show"
    ```

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 60" data-start="0"><b>HIT</b><br>fresh</div>
<div class="pashe-timeline__stale" style="flex: 600" data-start="60 s"><b>MISS</b> if the load succeeds, <b>STALE_IF_ERROR</b> if it raises one of if_error_on</div>
<div class="pashe-timeline__source" data-start="11 min"><b>the error</b><br>reaches the caller</div>
</div>

!!! warning "Narrow `if_error_on` to the errors of your source"

    By default it answers every `Exception`, so a bug of your own would be hidden behind a stale
    result too. Name the errors of the source, as `ConnectionError` and `TimeoutError` above.

### Stale items of a batch

When the function of a [batch](caching/batches.md) raises, the stale results of the items answer
instead, within `if_error`, only if each item the function loads has one: with one item short of a
stale result, the call raises, as the items are one call.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "caching_functions/batches_if_error_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "caching_functions/batches_if_error_async.py:show"
    ```

A batch waits for its load and loads nothing in the background, so it refuses `while_revalidate`,
`if_slow`, `lock_for` and `revalidate_before`.

!!! tip "A circuit breaker composes with it"

    Decorate the function with a breaker of another library, under the cache: while the breaker
    is open, its error is answered with the stale result without waiting for the source.

## Stale if slow

A slow source holds every call that waits for it. Within [`if_slow`][pashe.options.Stale(if_slow)],
once a call has waited [`slow_after`][pashe.options.Stale(slow_after)], the stale result answers,
and the load goes on in the background for the calls after it. One is refused without the other.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "staleness/if_slow_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "staleness/if_slow_async.py:show"
    ```

<div class="pashe-timeline">
<div class="pashe-timeline__source" style="flex: 20" data-start="0"><b>the call waits</b><br>for the load</div>
<div class="pashe-timeline__stale" style="flex: 80" data-start="0.2 s"><b>STALE_IF_SLOW</b><br>the stale result answers, the load goes on</div>
<div class="pashe-timeline__fresh" data-start="the load ends"><b>stored</b><br>for the next calls</div>
</div>

## How long the backend keeps a result

A result is fresh for `ttl`, and the backend keeps it longer by the longest window of `Stale`, so
a stale result is there to answer. With `@cache(ttl=60, stale=Stale(while_revalidate=30,
if_error=600))` the backend keeps it for 11 minutes:

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 60" data-start="0"><b>HIT</b><br>fresh</div>
<div class="pashe-timeline__stale" style="flex: 30" data-start="60 s"><b>STALE_WHILE_REVALIDATE</b><br>at once, a reload in the background</div>
<div class="pashe-timeline__stale" style="flex: 570" data-start="90 s"><b>STALE_IF_ERROR</b><br>only if the load raises</div>
<div class="pashe-timeline__source" data-start="11 min"><b>gone</b><br>the backend drops it</div>
</div>
