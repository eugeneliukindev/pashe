# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import Locks
from pashe.backends import SQLiteBackend

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = Locks(backend)


@locks.locked(ttl=30, key="report:{report_id}")  # every call under the lock of its key
def build(report_id: int) -> None: ...  # the work of yours for report_id


# --8<-- [end:show]
def main() -> None:
    build(1)
