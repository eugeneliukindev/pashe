# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.orjson import OrjsonCodec

cache = AsyncCache(AsyncMemoryBackend(), codec=OrjsonCodec())


@cache(ttl=60)
async def get_prices(category: str) -> dict[str, int]:
    return {"coffee": 990, "tea": 450} if category == "drinks" else {}  # what JSON holds, fast


# --8<-- [end:show]
async def main() -> None:
    await get_prices("drinks")
    assert await get_prices("drinks") == {"coffee": 990, "tea": 450}
