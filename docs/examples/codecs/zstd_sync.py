# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.zstd import ZstdCompressor

cache = Cache(
    MemoryBackend(), compressor=ZstdCompressor(level=3, min_size=1024)
)  # the defaults: faster than gzip for the same size


@cache(ttl=60)
def list_products(category: str) -> list[dict[str, str]]:
    return [{"category": category, "name": f"product {n}"} for n in range(100)]  # kilobytes of JSON


# --8<-- [end:show]
def main() -> None:
    stored = list_products("coffee")
    assert list_products("coffee") == stored
