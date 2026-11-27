import asyncio

# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncCache
from pashe.backends import AsyncSQLiteBackend

cache = AsyncCache(AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db"))
# --8<-- [end:show]


def close() -> None:
    asyncio.run(cache.aclose())  # the fixture that calls it runs outside any loop
