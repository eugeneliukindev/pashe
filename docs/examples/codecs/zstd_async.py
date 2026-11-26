# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.zstd import ZstdCompressor

cache = AsyncCache(
    AsyncMemoryBackend(), compressor=ZstdCompressor(level=3, min_size=1024)
)  # the defaults: faster than gzip for the same size


@cache(ttl=60)
async def list_products(category: str) -> list[dict[str, str]]:
    return [{"category": category, "name": f"product {n}"} for n in range(100)]  # kilobytes of JSON


# --8<-- [end:show]
async def main() -> None:
    stored = await list_products("coffee")
    assert await list_products("coffee") == stored
