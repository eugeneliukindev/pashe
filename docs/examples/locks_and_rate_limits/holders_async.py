# --8<-- [start:show]
import tempfile
from pathlib import Path

from pashe import AsyncLocks
from pashe.backends import AsyncSQLiteBackend

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
locks = AsyncLocks(backend)


@locks.locked(ttl=60, holders=3)  # at most three exports at once, in every process
async def export(tenant: str) -> None: ...  # the work of yours that a few may do together


async def main() -> None:
    async with locks.lock("reports", ttl=60, holders=3):  # the same for a block
        await export("acme")


# --8<-- [end:show]
