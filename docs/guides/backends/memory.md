# Memory

`MemoryBackend` keeps the entries in the memory of the process.

=== "Sync"

    ```python
    --8<-- "backends/memory_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/memory_async.py"
    ```

An LRU in the memory of this process, safe for threads. Other processes do not see its entries:
use it for tests, for a single process, as a fallback and as the local side of a near cache.

`max_entries` and `max_bytes` bound it: past either, the least recently used entries go first, a
live lock or counter only once nothing else is left, and a value larger than `max_bytes` alone
raises `ValueTooLargeError` instead of being stored.

---

API reference: [`pashe.backends`](../../reference/backends.md).
