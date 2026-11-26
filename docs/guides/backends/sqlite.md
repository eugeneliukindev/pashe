# SQLite

`SQLiteBackend` keeps the entries in a file of SQLite: `sqlite3` of the standard library, no
server and no extra.

=== "Sync"

    ```python
    --8<-- "backends/sqlite_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/sqlite_async.py"
    ```

The entries outlive a restart, and every process that opens the file shares them: the workers of
one machine, a CLI run after run, a desktop application. Locks, counters and rate limits hold
across the processes, as SQLite writes one at a time; a call waits up to 5 seconds for the write
of another process, then raises `BackendError`. `AsyncSQLiteBackend` runs every call in a thread,
so that wait blocks no task.

| | `MemoryBackend` | `SQLiteBackend` | `RedisBackend` |
| --- | --- | --- | --- |
| shared by | one process | the processes of one machine | every machine |
| after a restart | empty | the entries are there | the entries are there |
| needs | nothing | a local disk | a Redis server |

Expired entries are never returned; every write drops the expired ones. Keep the file on a local
disk: SQLite locks do not hold over a network file system. Other machines do not see the file:
for several machines take Redis.

---

API reference: [`SQLiteBackend`](../../reference/backends.md#pashe.backends.SQLiteBackend).
