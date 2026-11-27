# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede

cache = Cache(MemoryBackend())


class Report(TypedDict):
    id: int


@cache(ttl=60, stampede=Stampede(lock_for=5))  # one process loads, the others wait
def get_report(report_id: int) -> Report:
    return Report(id=report_id)  # the slow query of yours


# --8<-- [end:show]
def main() -> None:
    get_report(1)
