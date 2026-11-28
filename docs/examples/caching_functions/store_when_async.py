# --8<-- [start:show]
from datetime import timedelta

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Store

cache = AsyncCache(AsyncMemoryBackend())


@cache(ttl=timedelta(hours=1), key="order:{order_id}", store=Store(when=lambda order: order["status"] == "done"))
async def get_order(order_id: int) -> dict[str, str]:
    return {"status": "done" if order_id == 1 else "pending"}


# --8<-- [end:show]
async def main() -> None:
    # --8<-- [start:calls]
    await get_order(1)  # done: stored, the next call is a hit
    await get_order(2)  # pending: answered, not stored, the next call reloads
    # --8<-- [end:calls]
