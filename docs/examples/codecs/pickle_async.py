# --8<-- [start:show]
import os

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.codecs import PickleCodec

cache = AsyncCache(AsyncMemoryBackend(), codec=PickleCodec(secret=os.environ["CACHE_SECRET"]))


class Report:
    def __init__(self, day: str, rows: list[tuple[str, int]]) -> None:
        self.day = day
        self.rows = rows


@cache(ttl=60)
async def build_report(day: str) -> Report:
    return Report(day, [("coffee", 12)])  # any object pickle holds, signed with the secret


# --8<-- [end:show]
async def main() -> None:
    await build_report("2026-11-26")
    assert (await build_report("2026-11-26")).rows == [("coffee", 12)]
