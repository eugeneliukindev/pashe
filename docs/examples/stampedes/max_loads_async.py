# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stampede

cache = AsyncCache(AsyncMemoryBackend())


class Report(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(max_loads=2))  # two loads at once in this process
async def get_report(report_id: int) -> Report:
    return Report(id=report_id)  # the heavy query of yours


# --8<-- [end:show]
async def main() -> None:
    await get_report(1)
