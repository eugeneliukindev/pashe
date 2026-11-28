# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import Locks
from pashe.backends import SQLiteBackend

backend = SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = Locks(backend)


@locks.locked(ttl=60, holders=3)  # at most three exports at once, in every process
def export(tenant: str) -> None: ...  # the work of yours that a few may do together


def main() -> None:
    with locks.lock("reports", ttl=60, holders=3):  # the same for a block
        export("acme")


# --8<-- [end:show]
