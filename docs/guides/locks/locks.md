# Locks

`Locks` of `pashe`, `AsyncLocks` on the async side, takes locks that live in a backend, so every
process over it shares them: one holder at a time, in any process. `locks.lock`, `locks.try_lock`
and `@locks.locked` take one. The locks live apart from the entries of a cache over the same
backend and `prefix`, and close nothing: the backend belongs to whoever made it.

!!! info "Where it works"

    In the backend: every process of every machine over Redis, every process of one machine over
    SQLite, one process over memory. See [Where each feature works](../choosing.md#where-each-feature-works).

!!! tip "A lock for a cached function is `Stampede(lock_for=...)`"

    A waiter of `@locks.locked` runs the function itself once the lock is free. To load a cached
    result once for the whole service, with the waiters taking that result, give the cached function
    `stampede=Stampede(lock_for=...)` instead: see [Locking a load across processes](../failures/stampedes.md#locking-a-load-across-processes).

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/lock_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/lock_async.py:show"
    ```

```mermaid
sequenceDiagram
    box rgba(43,91,132,0.14) Process 1
        participant A as with locks.lock
    end
    box rgba(0,150,136,0.14) Process 2
        participant B as with locks.lock
    end
    box rgba(247,181,0,0.18) Redis: every process
        participant R as Redis
    end
    A->>R: take "report" for 30 s
    B->>R: take "report": held, wait
    loop every 10 s while the block runs
        A->>R: extend to 30 s
    end
    A->>R: release
    R-->>B: taken
    Note over R: a process that dies frees the lock after 30 s
```

`locks.lock` and `locks.try_lock` return a `Lock` of `pashe.locks`, an `AsyncLock` on the async
side; its `key` is the name it was given. Entering waits while someone else holds the lock;
`timeout` bounds the wait and raises
`LockTimeoutError`. While the block runs the lock is extended every third of `ttl`, so the block
may run longer than `ttl`; the `ttl` frees the lock if the process dies.

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/try_lock_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/try_lock_async.py:show"
    ```

!!! warning "A lost lock"

    If the lock expires while the block runs, as when Redis was unreachable for longer than
    `ttl`, someone else may hold it now, and `LockLostError` is raised: a sync block runs to its
    end first, as a thread cannot be interrupted; an async block is cancelled at once.

API reference: [`Locks`](../../reference/caches.md#pashe.Locks),
[`Locks.lock`](../../reference/caches.md#pashe.Locks.lock),
[`Locks.try_lock`](../../reference/caches.md#pashe.Locks.try_lock),
[`Locks.locked`](../../reference/caches.md#pashe.Locks.locked),
[`Lock`](../../reference/locks.md#pashe.locks.Lock),
[`LockTimeoutError`](../../reference/errors.md#pashe.errors.LockTimeoutError),
[`LockLostError`](../../reference/errors.md#pashe.errors.LockLostError).

## Every option

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/lock_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/lock_options_async.py:show"
    ```

## Several holders

`holders` lets a lock be held by that many at once, as a semaphore across processes: a fourth
waits while three hold `holders=3`. `lock`, `try_lock` and `@locks.locked` take it, and every
holder is extended and released on its own.

=== "Sync"

    ```python
    --8<-- "locks_and_rate_limits/holders_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "locks_and_rate_limits/holders_async.py:show"
    ```

!!! warning "One number of holders for a key"

    Every use of a key takes the same `holders`. Each holder takes one of as many keys in the
    backend, the first of them the key itself; a lock of the key with fewer holders checks fewer
    of them, and lets more in than either number says.

---

API reference: [`pashe.locks`](../../reference/locks.md).
