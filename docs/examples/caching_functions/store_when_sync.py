# --8<-- [start:show]
from datetime import timedelta

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Store

cache = Cache(MemoryBackend())


@cache(ttl=timedelta(hours=1), key="order:{order_id}", store=Store(when=lambda order: order["status"] == "done"))
def get_order(order_id: int) -> dict[str, str]:
    return {"status": "done" if order_id == 1 else "pending"}


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_order(1)  # done: stored, the next call is a hit
    get_order(2)  # pending: answered, not stored, the next call reloads
    # --8<-- [end:calls]
