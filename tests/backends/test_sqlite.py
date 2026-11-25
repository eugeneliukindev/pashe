"""What only the SQLite backend does: a file that outlives the object, and processes that share it."""

from __future__ import annotations

import asyncio
import sqlite3
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from pashe.backends import AsyncSQLiteBackend, SQLiteBackend
from pashe.errors import BackendError

if TYPE_CHECKING:
    from pathlib import Path

    from tests.harness.helpers import Clock

_PROCESSES = 4
_INCREMENTS = 200
_COUNT = """
from pashe.backends import AsyncSQLiteBackend, SQLiteBackend
backend = SQLiteBackend({path!r})
for _ in range({increments}):
    backend.incr("hits", 1)
backend.close()
"""


def test_entries_outlive_the_backend_that_wrote_them(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    writer = SQLiteBackend(path)
    writer.set("k", b"v", ttl=60)
    writer.close()

    reader = SQLiteBackend(path)
    found = reader.get("k")
    reader.close()

    assert found == b"v"


def test_an_expired_entry_is_a_miss_and_free_for_set_if_absent(tmp_path: Path, clock: Clock) -> None:
    backend = SQLiteBackend(tmp_path / "cache.db", clock=clock)
    backend.set("lock", b"old", ttl=10)
    clock.now += 10

    taken = backend.set_if_absent("lock", b"new", ttl=10)
    held = backend.get("lock")
    backend.close()

    assert (taken, held) == (True, b"new")


def test_get_many_reads_more_keys_than_one_statement_takes(tmp_path: Path) -> None:
    backend = SQLiteBackend(tmp_path / "cache.db")
    keys = [f"k{index}" for index in range(2500)]
    backend.set_many(dict.fromkeys(keys, b"v"))

    found = backend.get_many([*keys, "missing", "k0"])
    backend.close()

    assert found == [b"v"] * 2500 + [None, b"v"]


def test_counters_hold_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    SQLiteBackend(path).close()  # the table exists before the processes race to make it
    count = _COUNT.format(path=str(path), increments=_INCREMENTS)

    processes = [subprocess.Popen([sys.executable, "-c", count]) for _ in range(_PROCESSES)]  # noqa: S603 - this Python
    codes = [process.wait() for process in processes]

    backend = SQLiteBackend(path)
    hits = backend.get("hits")
    backend.close()
    assert codes == [0] * _PROCESSES
    assert hits == str(_PROCESSES * _INCREMENTS).encode()


def test_a_file_that_cannot_be_opened_is_a_backend_error(tmp_path: Path) -> None:
    with pytest.raises(BackendError, match="sqlite"):
        SQLiteBackend(tmp_path / "missing" / "cache.db")


def test_a_file_that_is_not_a_database_is_a_backend_error(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    path.write_bytes(b"x" * 4096)

    with pytest.raises(BackendError, match="not a database"):
        SQLiteBackend(path)


@pytest.mark.no_leaks(threads=False)  # fails the test if the loop is blocked
async def test_an_async_call_waits_for_a_busy_file_in_a_thread_not_in_the_loop(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    backend = AsyncSQLiteBackend(path)
    writer = sqlite3.connect(path, isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")  # another process holds the write lock
    asyncio.get_running_loop().call_later(0.3, writer.commit)  # which the loop can run only if it is free

    await backend.set("k", b"v")

    writer.close()
    assert await backend.get("k") == b"v"
    await backend.aclose()
