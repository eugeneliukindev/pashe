# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede

cache = Cache(MemoryBackend())


class Report(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(max_loads=2))  # two loads at once in this process
def get_report(report_id: int) -> Report:
    return Report(id=report_id)  # the heavy query of yours


# --8<-- [end:show]
def main() -> None:
    get_report(1)
