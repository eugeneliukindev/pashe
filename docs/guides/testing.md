# Testing

How to test code that caches: a cache of its own for each test, time that moves without sleeping,
and the same tests against Redis.

## A memory backend per test

Code under test takes its cache from outside, so a test gives it one of its own, in memory: no
Redis, and no entries leak from one test into another.

=== "Sync"

    ```python
    --8<-- "testing/loaded_once_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "testing/loaded_once_async.py:show"
    ```

## Time without sleeping

A cache asks its `clock` for the wall time, and a memory backend asks its own for when entries
expire. A test moves them instead of sleeping:

=== "Sync"

    ```python
    --8<-- "testing/stale_clock_sync.py:imports"
    --8<-- "testing/stale_clock_sync.py:show"
    --8<-- "testing/stale_clock_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "testing/stale_clock_async.py:imports"
    --8<-- "testing/stale_clock_async.py:show"
    --8<-- "testing/stale_clock_async.py:calls"
    ```

A hook's `on_call` tells how every call was answered, so a test checks the behaviour of the cache,
not only the results.

## Against Redis

The behaviour that depends on Redis itself, such as a near cache over two processes or a bus,
deserves a test against a real one. [testcontainers](https://testcontainers.com) starts one for
the session:

=== "Sync"

    ```python
    --8<-- "testing/redis_container_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "testing/redis_container_async.py"
    ```

---
