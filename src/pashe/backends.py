"""Places where entries live, and the base classes of your own.

The near cache puts a small cache in memory in front of a shared backend such as Redis:
hot keys are read from memory, and reads go on for a while when the shared backend is slow.
Writes and deletes go to the shared backend and drop the local copy; counters, locks and TTLs
always use the shared backend. A bus of pashe.invalidation tells the other near caches which keys
changed.

SQLiteBackend keeps entries in a file: they outlive a restart, and every process on the machine
shares them, with no server.

A breaker decides whether a call may reach the server of a backend: CircuitBreaker skips it for a
while after it failed several times in a row, so a server that is down costs no wait per call.
"""

from pashe._internal.async_.backends.backend import AsyncBackend
from pashe._internal.async_.backends.memory import AsyncMemoryBackend
from pashe._internal.async_.backends.near import AsyncNearCacheBackend
from pashe._internal.breakers import Breaker, CircuitBreaker, NoOpBreaker
from pashe._internal.sqlite import AsyncSQLiteBackend, SQLiteBackend
from pashe._internal.sync.backends.backend import Backend
from pashe._internal.sync.backends.memory import MemoryBackend
from pashe._internal.sync.backends.near import NearCacheBackend

__all__ = [
    "AsyncBackend",
    "AsyncMemoryBackend",
    "AsyncNearCacheBackend",
    "AsyncSQLiteBackend",
    "Backend",
    "Breaker",
    "CircuitBreaker",
    "MemoryBackend",
    "NearCacheBackend",
    "NoOpBreaker",
    "SQLiteBackend",
]
