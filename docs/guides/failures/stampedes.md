# Stampede protection

When a popular key expires, every caller misses at once and asks the source. The options of
`Stampede`, from `pashe.options`, share the load.

| Option | Type | Where | Default | What it does |
| --- | --- | --- | --- | --- |
| `single_flight` | `bool` | one process | `True` | concurrent calls of a key share one lookup and one load |
| `lock_for` | `float | int | timedelta` | every process | `0`, off | a missing key loads under a lock in the backend: one process loads, the others wait and take its result |
| `max_concurrent_loads` | `int` | one process | `0`, no limit | at most this many loads of the function run at once |
| `revalidate_before` | `float | int | timedelta` | every process | `0`, off | in the last seconds of the TTL a call gets the fresh result at once, and one caller reloads it in the background |

=== "Sync"

    ```python
    --8<-- "stampedes/lock_for_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "stampedes/lock_for_async.py:show"
    ```

`lock_for` is the longest the lock is held, so a process that dies holding it frees it.

!!! warning "Concurrent callers share one object"

    With `single_flight` concurrent callers of a key get the same object: copy a result before
    you change it.

A call over `max_concurrent_loads` waits for a slot, or raises `OverloadedError` when a stale
result can answer it instead, so a stale window answers it.

## Sharing a load within a process

Calls of one key at the same time in one process share one load. It is on by default.

=== "Without"

    ```mermaid
    sequenceDiagram
        box rgba(43,91,132,0.14) Process 1
            participant A as Call 1
            participant B as Call 2
        end
        participant DB as Source
        A->>DB: miss, load
        B->>DB: miss, load
        Note over DB: two loads of one key
    ```

=== "With"

    ```mermaid
    sequenceDiagram
        box rgba(43,91,132,0.14) Process 1
            participant A as Call 1
            participant B as Call 2
        end
        participant DB as Source
        A->>DB: miss, load
        B->>A: miss, wait for its load
        DB-->>A: result
        A-->>B: the same result
        Note over DB: one load
    ```

## Locking a load across processes

`single_flight` leaves one load per process; with ten processes that is ten loads. A load lock
in Redis leaves one for all of them.

=== "Without"

    ```mermaid
    sequenceDiagram
        box rgba(43,91,132,0.14) Process 1
            participant A as Calls
        end
        box rgba(0,150,136,0.14) Process 2
            participant B as Calls
        end
        box rgba(247,181,0,0.18) Redis: every process
            participant R as Redis
        end
        participant DB as Source
        A->>R: miss
        B->>R: miss
        A->>DB: load
        B->>DB: load
        Note over DB: one load per process
    ```

=== "With"

    ```mermaid
    sequenceDiagram
        box rgba(43,91,132,0.14) Process 1
            participant A as Calls
        end
        box rgba(0,150,136,0.14) Process 2
            participant B as Calls
        end
        box rgba(247,181,0,0.18) Redis: every process
            participant R as Redis
        end
        participant DB as Source
        A->>R: miss, take the lock, held at most lock_for
        B->>R: miss, the lock is taken: wait
        A->>DB: load
        A->>R: store, release the lock
        R-->>B: the stored result
        Note over DB: one load for every process
    ```

## Limiting loads at once

A limit of loads of one function in one process, whatever their keys: here, `max_concurrent_loads=2`.

=== "Without"

    ```mermaid
    sequenceDiagram
        box rgba(43,91,132,0.14) Process 1
            participant C as get_report(1), (2), (3)
        end
        participant DB as Source
        C->>DB: load 1
        C->>DB: load 2
        C->>DB: load 3
        Note over DB: three heavy loads at once
    ```

=== "With"

    ```mermaid
    sequenceDiagram
        box rgba(43,91,132,0.14) Process 1
            participant C as get_report(1), (2), (3)
        end
        participant DB as Source
        C->>DB: load 1
        C->>DB: load 2
        Note over C: 3 waits for a slot, or a stale result answers it
        DB-->>C: report 1
        C->>DB: load 3, in the freed slot
    ```

## Reload before the TTL

A key read all the time still expires, and the calls right after it miss or answer stale. With
`revalidate_before` the result is reloaded while it is still fresh: here, the calls of its last
10 seconds get it at once, a HIT, and one caller reloads it in the background.

```mermaid
flowchart LR
    fresh["0 to 50 s<br/>fresh: HIT"] --> ahead["50 to 60 s<br/>fresh at once, a reload in the background: HIT"]
    ahead --> reloaded["the reloaded result, fresh for 60 s more"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    class fresh,ahead,reloaded fromCache
```

=== "Sync"

    ```python
    --8<-- "stampedes/revalidate_before_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "stampedes/revalidate_before_async.py:show"
    ```

The reload holds a lock in the backend, so one process reloads a key at a time; a failed reload
goes to `on_error`, and the result answers until its TTL, then as `Stale` says. A key nobody
reads in those seconds expires as without it. Unlike `Stale(while_revalidate=...)`, no call
gets a result past its TTL; the price is a load a little more often. A batch takes none.

---

API reference: [options](../../reference/options.md).
