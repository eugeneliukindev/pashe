# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.compressors import GzipCompressor

cache = AsyncCache(
    AsyncMemoryBackend(), compressor=GzipCompressor(level=6, min_size=1024)
)  # the defaults: values of 1 KiB or more


@cache(ttl=60)
async def list_products(category: str) -> list[dict[str, str]]:
    return [{"category": category, "name": f"product {n}"} for n in range(100)]  # kilobytes of JSON


# --8<-- [end:show]
async def main() -> None:
    stored = await list_products("coffee")
    assert await list_products("coffee") == stored
