# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import Locks
from pashe.backends import SQLiteBackend

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = Locks(backend)


def build_report() -> None: ...  # the work of yours that one process at a time may do


lock = locks.try_lock("report", ttl=30)  # the lock if it is free now, else None
if lock is not None:
    with lock:
        build_report()


# --8<-- [end:show]
