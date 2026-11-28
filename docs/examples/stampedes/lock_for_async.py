# --8<-- [start:show]
import tempfile
from pathlib import Path
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncSQLiteBackend
from pashe.options import Stampede

cache = AsyncCache(AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db"))  # every process of the machine


class Report(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(lock_for=5))  # one process loads, the others wait
async def get_report(report_id: int) -> Report:
    return Report(id=report_id)  # the slow query of yours


# --8<-- [end:show]
async def main() -> None:
    await get_report(1)
