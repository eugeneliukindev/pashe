# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.orjson import OrjsonCodec

cache = Cache(MemoryBackend(), codec=OrjsonCodec())


@cache(ttl=60)
def get_prices(category: str) -> dict[str, int]:
    return {"coffee": 990, "tea": 450} if category == "drinks" else {}  # what JSON holds, fast


# --8<-- [end:show]
def main() -> None:
    get_prices("drinks")
    assert get_prices("drinks") == {"coffee": 990, "tea": 450}
