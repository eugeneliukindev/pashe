# SQLite

[`SQLiteBackend`][pashe.backends.SQLiteBackend] keeps entries in an SQLite file. It uses `sqlite3`
from the standard library, so you need no server and no extra.

=== "Sync"

    ```python
    --8<-- "backends/sqlite_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "backends/sqlite_async.py"
    ```

The entries survive a restart, and every process that opens the file shares them. Think of the
workers on one machine, a CLI from one run to the next, or a desktop app.

Locks, counters and rate limits work across processes, because SQLite writes one at a time. A call
waits up to 5 seconds for another process's write, then raises `BackendError`.
[`AsyncSQLiteBackend`][pashe.backends.AsyncSQLiteBackend] runs every call in a thread, so that wait
doesn't block any task.

| | `MemoryBackend` | `SQLiteBackend` | `RedisBackend` |
| --- | --- | --- | --- |
| shared by | one process | the processes of one machine | every machine |
| after a restart | empty | the entries are there | the entries are there |
| needs | nothing | a local disk | a Redis server |

Expired entries are never returned, and every write drops them. Keep the file on a local disk:
SQLite locks don't work over a network file system. Other machines don't see the file, so for
several machines, use Redis.
