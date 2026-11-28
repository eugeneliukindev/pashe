# Stale results

A stored result past its TTL is stale. Often a stale result is better than none:
[`Stale`][pashe.options.Stale], from `pashe.options`, lets calls get it for a while longer. Each
stale window covers one case: while the result is [reloaded](#stale-while-revalidate), when the
source [fails](#stale-if-error), and when it's [slow](#stale-if-slow).

Every window is off until you set it. The backend keeps a result long enough for each window, so a
stale result works in every process. See
[How long the backend keeps a result](#how-long-the-backend-keeps-a-result).

## Stale while revalidate

Right after the TTL, a call would have to wait for the reload. Within
[`while_revalidate`][pashe.options.Stale(while_revalidate)], the call gets the stale result right
away, and one caller reloads it in the background.

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

While the window lasts, no caller waits for the source. Want to reload before the result goes
stale? See [Reload before the TTL](stampedes.md#reload-before-the-ttl).

## Stale if error

Your source goes down. Without a stale result, the call raises. Within
[`if_error`][pashe.options.Stale(if_error)], a call that hits one of the
[`if_error_on`][pashe.options.Stale(if_error_on)] errors gets the stale result instead, and the
error goes to `on_error`.

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

    By default it covers every `Exception`, so a stale result would hide your own bugs too. Name
    your source's errors, like `ConnectionError` and `TimeoutError` above.

### Stale items of a batch

When a [batch](caching/batches.md) function raises, the call can get the items' stale results
instead, within `if_error`. But only if every item the function loads has one. If even one item
has no stale result, the call raises, since the items are one call.

=== "Sync"

    ```python hl_lines="14"
    --8<-- "caching_functions/batches_if_error_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="14"
    --8<-- "caching_functions/batches_if_error_async.py:show"
    ```

A batch waits for its load and never loads in the background. So it refuses `while_revalidate`,
`if_slow`, `lock_for` and `revalidate_before`.

!!! tip "A circuit breaker composes with it"

    Decorate the function with a breaker from another library, under the cache. While the breaker
    is open, the call gets the stale result for its error, without waiting for the source.

## Stale if slow

A slow source holds up every call that waits for it. Within
[`if_slow`][pashe.options.Stale(if_slow)], once a call has waited
[`slow_after`][pashe.options.Stale(slow_after)], it gets the stale result. The load goes on in the
background for the calls after it. You need to set both: pashe refuses one without the other.

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

A result is fresh for `ttl`. The backend keeps it longer, by the longest window of `Stale`, so
the stale result is still there when a call needs it. With `@cache(ttl=60,
stale=Stale(while_revalidate=30, if_error=600))`, the backend keeps it for 11 minutes:

<div class="pashe-timeline">
<div class="pashe-timeline__fresh" style="flex: 60" data-start="0"><b>HIT</b><br>fresh</div>
<div class="pashe-timeline__stale" style="flex: 30" data-start="60 s"><b>STALE_WHILE_REVALIDATE</b><br>at once, a reload in the background</div>
<div class="pashe-timeline__stale" style="flex: 570" data-start="90 s"><b>STALE_IF_ERROR</b><br>only if the load raises</div>
<div class="pashe-timeline__source" data-start="11 min"><b>gone</b><br>the backend drops it</div>
</div>
