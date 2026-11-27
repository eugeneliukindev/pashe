# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import Cache
from pashe.backends import SQLiteBackend

cache = Cache(SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db"))
# --8<-- [end:show]


def close() -> None:
    cache.close()
