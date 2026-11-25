# --8<-- [start:imports]
from typing import override

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.hooks import CacheStatus, Hook, Outcome
from pashe.options import Stale

# --8<-- [end:imports]


# --8<-- [start:show]
class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


clock = Clock()
statuses: list[CacheStatus] = []


class RecordStatus(Hook):
    @override
    def on_call(self, outcome: Outcome, /) -> None:
        statuses.append(outcome.status)


cache = Cache(MemoryBackend(clock=clock), hooks=[RecordStatus()], clock=clock)


@cache(ttl=60, stale=Stale(while_revalidate=30))
def get_rate() -> float:
    return 0.92


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_rate()
    clock.now += 70  # past the TTL, inside the stale window
    get_rate()
    cache.close()  # waits for the reload in the background
    assert statuses == [CacheStatus.MISS, CacheStatus.STALE_WHILE_REVALIDATE]
    # --8<-- [end:calls]
