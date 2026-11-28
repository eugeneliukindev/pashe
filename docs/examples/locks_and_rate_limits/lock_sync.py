# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import Locks
from pashe.backends import SQLiteBackend

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = Locks(backend)


def build_report() -> None: ...  # the work of yours that one process at a time may do


with locks.lock("report", ttl=30):
    build_report()


# --8<-- [end:show]
