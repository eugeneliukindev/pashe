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

---

API reference: [`pashe.backends`](../../reference/backends.md).
