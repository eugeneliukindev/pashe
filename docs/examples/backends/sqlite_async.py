import tempfile
from pathlib import Path

from pashe import AsyncCache
from pashe.backends import AsyncSQLiteBackend

cache = AsyncCache(AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db"))
