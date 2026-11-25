import tempfile
from pathlib import Path

from pashe import Cache
from pashe.backends import SQLiteBackend

cache = Cache(SQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db"))
