# --8<-- [start:show]
import os

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.codecs import PickleCodec

cache = Cache(MemoryBackend(), codec=PickleCodec(secret=os.environ["CACHE_SECRET"]))


class Report:
    def __init__(self, day: str, rows: list[tuple[str, int]]) -> None:
        self.day = day
        self.rows = rows


@cache(ttl=60)
def build_report(day: str) -> Report:
    return Report(day, [("coffee", 12)])  # any object pickle holds, signed with the secret


# --8<-- [end:show]
def main() -> None:
    build_report("2026-11-26")
    assert (build_report("2026-11-26")).rows == [("coffee", 12)]
