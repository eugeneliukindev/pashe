from __future__ import annotations

import asyncio
import contextlib
import itertools
import math
import os
import sqlite3
import threading
import time
from typing import TYPE_CHECKING, Final, final, override

from pashe._internal.async_.backends.backend import AsyncBackend
from pashe._internal.checks import FUNCTION, expect_int64, expect_type, parse_counter
from pashe._internal.sync.backends.backend import Backend
from pashe.errors import BackendError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping, Sequence

# Every entry in one table; expires_at is a Unix time, the same for every process, NULL never
# expires. An entry is live while expires_at IS NULL OR expires_at > now.
# WAL lets readers go on while one writes; a cache may lose its last writes on a power cut.
_SCHEMA: Final = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS pashe_entries (key TEXT PRIMARY KEY, value BLOB NOT NULL, expires_at REAL) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS pashe_entries_expiry ON pashe_entries (expires_at);
"""
# the errors of a statement SQLite refused, past the failures of the file
_BUGS: Final = (
    sqlite3.DataError,
    sqlite3.IntegrityError,
    sqlite3.InternalError,
    sqlite3.NotSupportedError,
    sqlite3.ProgrammingError,
)
_MAX_KEYS_PER_QUERY: Final = 900  # under 999, the fewest variables a statement of an old SQLite takes
_BUSY_TIMEOUT: Final = 5.0  # seconds a call waits for the write of another process, as sqlite3 waits by default

_GET_MANY: Final = (  # {} takes a placeholder per key
    "SELECT key, value FROM pashe_entries WHERE key IN ({}) AND (expires_at IS NULL OR expires_at > ?)"
)
_GET_WITH_EXPIRY: Final = (
    "SELECT value, expires_at FROM pashe_entries WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)"
)
_SET: Final = (
    "INSERT INTO pashe_entries VALUES (?, ?, ?)"
    " ON CONFLICT (key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at"
)
_SET_IF_ABSENT: Final = (  # the update runs only over an expired entry
    "INSERT INTO pashe_entries VALUES (?, ?, ?)"
    " ON CONFLICT (key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at"
    " WHERE pashe_entries.expires_at IS NOT NULL AND pashe_entries.expires_at <= ?"
)
_PURGE: Final = "DELETE FROM pashe_entries WHERE expires_at <= ?"
_DELETE: Final = "DELETE FROM pashe_entries WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)"
_DELETE_IF_EQUALS: Final = (
    "DELETE FROM pashe_entries WHERE key = ? AND (expires_at IS NULL OR expires_at > ?) AND value = ?"
)
_EXPIRE: Final = "UPDATE pashe_entries SET expires_at = ? WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)"
_EXPIRE_IF_EQUALS: Final = (
    "UPDATE pashe_entries SET expires_at = ? WHERE key = ? AND (expires_at IS NULL OR expires_at > ?) AND value = ?"
)


@final
class SQLiteBackend(Backend):
    """A backend in a file of SQLite: it outlives a restart, and every process on the machine shares it.

    It needs no server and no extra: sqlite3 of the standard library. Every process that opens the
    file sees the same entries, and locks, counters and rate limits hold across them, as SQLite
    writes one at a time. Expired entries are never returned; a write drops them. Keep the file on
    a local disk: SQLite locks do not hold over a network file system.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import SQLiteBackend
        >>> cache = Cache(SQLiteBackend(":memory:"))
        >>> cache.close()
    """

    __slots__ = ("_clock", "_connection", "_lock")

    def __init__(self, path: str | os.PathLike[str], /, *, clock: Callable[[], float] = time.time) -> None:
        """Open the file, creating it and its table if absent.

        Args:
            path: the file, such as ``"/var/cache/app.db"``; ``":memory:"`` keeps the entries in
                this object alone.
            clock: seconds of the Unix time, which every process reads alike; for tests.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            BackendError: the file cannot be opened or written.
        """
        expect_type("path", path, str | os.PathLike)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        expect_type("clock", clock, FUNCTION)

        self._clock = clock

        self._lock = threading.Lock()  # one connection for every thread: a transaction at a time
        with _translated_errors():
            self._connection = sqlite3.connect(
                path, timeout=_BUSY_TIMEOUT, isolation_level=None, check_same_thread=False
            )
            try:
                self._connection.executescript(_SCHEMA)
            except BaseException:
                self._connection.close()
                raise

    @override
    def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        found: dict[str, bytes] = {}
        with self._lock, _translated_errors():
            now = self._clock()
            for part in itertools.batched(dict.fromkeys(keys), _MAX_KEYS_PER_QUERY):
                query = _GET_MANY.format(", ".join("?" * len(part)))
                found.update(self._connection.execute(query, (*part, now)).fetchall())
        return [found.get(key) for key in keys]

    @override
    def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        with self._lock, _translated_errors(), self._transaction():
            now = self._clock()
            expires_at = _expires_at(now, ttl)
            self._connection.executemany(_SET, [(key, value, expires_at) for key, value in values.items()])
            self._connection.execute(_PURGE, (now,))

    @override
    def set_if_absent(self, key: str, value: bytes, /, *, ttl: float | None = None) -> bool:
        with self._lock, _translated_errors():
            now = self._clock()
            return self._connection.execute(_SET_IF_ABSENT, (key, value, _expires_at(now, ttl), now)).rowcount > 0

    @override
    def delete(self, key: str, /) -> bool:
        with self._lock, _translated_errors():
            return self._connection.execute(_DELETE, (key, self._clock())).rowcount > 0

    @override
    def incr(self, key: str, by: int, /, *, ttl: float | None = None) -> int:
        expect_int64("sqlite.by", by)
        with self._lock, _translated_errors(), self._transaction():
            now = self._clock()
            row = self._connection.execute(_GET_WITH_EXPIRY, (key, now)).fetchone()
            value, expires_at = (b"0", _expires_at(now, ttl)) if row is None else row
            new = parse_counter("sqlite", value) + by
            expect_int64("sqlite.result", new)
            self._connection.execute(_SET, (key, str(new).encode(), expires_at))
            return new

    @override
    def expire(self, key: str, ttl: float, /) -> bool:
        with self._lock, _translated_errors():
            now = self._clock()
            return self._connection.execute(_EXPIRE, (now + ttl, key, now)).rowcount > 0

    @override
    def ttl(self, key: str, /) -> float | None:
        with self._lock, _translated_errors():
            now = self._clock()
            row = self._connection.execute(_GET_WITH_EXPIRY, (key, now)).fetchone()
        if row is None:
            return None
        return math.inf if row[1] is None else row[1] - now

    @override
    def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        with self._lock, _translated_errors():
            return self._connection.execute(_DELETE_IF_EQUALS, (key, self._clock(), value)).rowcount > 0

    @override
    def expire_if_equals(self, key: str, value: bytes, ttl: float, /) -> bool:
        with self._lock, _translated_errors():
            now = self._clock()
            return self._connection.execute(_EXPIRE_IF_EQUALS, (now + ttl, key, now, value)).rowcount > 0

    @override
    def ping(self) -> None:
        with self._lock, _translated_errors():
            self._connection.execute("SELECT 1")

    @override
    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextlib.contextmanager
    def _transaction(self) -> Generator[None]:
        # IMMEDIATE takes the write lock at once: a read and the write after it see no other writer between
        self._connection.execute("BEGIN IMMEDIATE")
        with self._connection:  # commits, or rolls back when the block or the commit fails
            yield


@final
class AsyncSQLiteBackend(AsyncBackend):
    """SQLiteBackend for AsyncCache: every call runs in a thread, so a wait for the file blocks no task.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncSQLiteBackend
        >>> cache = AsyncCache(AsyncSQLiteBackend(":memory:"))
        >>> import asyncio
        >>> asyncio.run(cache.aclose())
    """

    __slots__ = ("_sync",)

    def __init__(self, path: str | os.PathLike[str], /, *, clock: Callable[[], float] = time.time) -> None:
        """Open the file, creating it and its table if absent.

        Args:
            path: the file, such as ``"/var/cache/app.db"``; ``":memory:"`` keeps the entries in
                this object alone.
            clock: seconds of the Unix time, which every process reads alike; for tests.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            BackendError: the file cannot be opened or written.
        """
        self._sync = SQLiteBackend(path, clock=clock)

    @override
    async def get_many(self, keys: Sequence[str], /) -> list[bytes | None]:
        return await asyncio.to_thread(self._sync.get_many, keys)

    @override
    async def set_many(self, values: Mapping[str, bytes], /, *, ttl: float | None = None) -> None:
        await asyncio.to_thread(self._sync.set_many, values, ttl=ttl)

    @override
    async def set_if_absent(self, key: str, value: bytes, /, *, ttl: float | None = None) -> bool:
        return await asyncio.to_thread(self._sync.set_if_absent, key, value, ttl=ttl)

    @override
    async def delete(self, key: str, /) -> bool:
        return await asyncio.to_thread(self._sync.delete, key)

    @override
    async def incr(self, key: str, by: int, /, *, ttl: float | None = None) -> int:
        return await asyncio.to_thread(self._sync.incr, key, by, ttl=ttl)

    @override
    async def expire(self, key: str, ttl: float, /) -> bool:
        return await asyncio.to_thread(self._sync.expire, key, ttl)

    @override
    async def ttl(self, key: str, /) -> float | None:
        return await asyncio.to_thread(self._sync.ttl, key)

    @override
    async def delete_if_equals(self, key: str, value: bytes, /) -> bool:
        return await asyncio.to_thread(self._sync.delete_if_equals, key, value)

    @override
    async def expire_if_equals(self, key: str, value: bytes, ttl: float, /) -> bool:
        return await asyncio.to_thread(self._sync.expire_if_equals, key, value, ttl)

    @override
    async def ping(self) -> None:
        await asyncio.to_thread(self._sync.ping)

    @override
    async def aclose(self) -> None:
        await asyncio.to_thread(self._sync.close)


def _expires_at(now: float, ttl: float | None) -> float | None:
    return None if ttl is None else now + ttl


@contextlib.contextmanager
def _translated_errors() -> Generator[None]:
    # A file locked too long, full, unreadable or not a database is a failure of the backend: an
    # OperationalError, or a bare DatabaseError for a corrupt file. Its other subclasses are bugs.
    try:
        yield
    except _BUGS:
        raise
    except sqlite3.DatabaseError as error:
        msg = f"sqlite: {error}"
        raise BackendError(msg) from error
