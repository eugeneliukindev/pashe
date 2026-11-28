# Testing

This page shows how to test code that caches. Each test gets its own cache, time moves forward
without sleeping, and the same tests run against Redis.

## A memory backend per test

Your code under test takes its cache from outside. So each test can hand it a cache of its own,
in memory. You don't need Redis, and no entries leak from one test into the next.

=== "Sync"

    ```python
    --8<-- "testing/loaded_once_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "testing/loaded_once_async.py:show"
    ```

!!! note "A warning about options that share across processes"

    Some options only pay off over a backend that other processes see, such as
    [`lock_for`][pashe.options.Stampede(lock_for)], or a near cache in front of shared memory. Over a
    memory backend they still work, but pashe warns with
    [`OneProcessWarning`][pashe.errors.OneProcessWarning], as in production they'd mean a mistake.
    In tests that swap Redis for memory on purpose, turn that one warning off, and keep every other:

    ```toml
    [tool.pytest.ini_options]
    filterwarnings = ["error", "ignore::pashe.errors.OneProcessWarning"]
    ```

## Time without sleeping

A cache asks its `clock` for the wall time, and a memory backend asks its own clock when entries
expire. In a test, you move both clocks forward instead of sleeping:

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

A hook's `on_call` hears how each call was answered. So your test can check how the cache
behaves, not only what it returns.

## Against Redis

Some behaviour depends on Redis itself, such as a near cache over two processes, or a bus. That
deserves a test against a real Redis. [testcontainers](https://testcontainers.com) starts one for
the test session:

=== "Sync"

    ```python
    --8<-- "testing/redis_container_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "testing/redis_container_async.py"
    ```

---
