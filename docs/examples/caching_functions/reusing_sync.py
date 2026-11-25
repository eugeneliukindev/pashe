# ruff: noqa: E402 - the page shows these imports after what it leaves out
# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


class Plan(TypedDict):
    id: int


import functools

from pashe.options import Stale, Stampede

RESILIENT = Stale(while_revalidate=30, if_error=300)
resilient = functools.partial(cache, stale=RESILIENT, stampede=Stampede(jitter=0.1))


@resilient(ttl=60)
def get_plan(plan_id: int) -> Plan:

    # --8<-- [end:show]
    return Plan(id=plan_id)
