# Memory

[`MemoryBackend`][pashe.backends.MemoryBackend] keeps entries in the process's own memory.

=== "Sync"

    ```python
    --8<-- "backends/memory_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/memory_async.py"
    ```

Other processes don't see its entries. Use it for tests, for a single process, as a fallback, and
as the local side of a near cache.

You can cap its size with [`max_entries`][pashe.backends.MemoryBackend(max_entries)] and
[`max_bytes`][pashe.backends.MemoryBackend(max_bytes)]. When it goes past either one, the least
recently used entries go first. A live lock or counter goes only when nothing else is left. A
single value bigger than `max_bytes` isn't stored: it raises `ValueTooLargeError`.
