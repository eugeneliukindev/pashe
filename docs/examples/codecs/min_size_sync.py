# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.compressors import GzipCompressor

cache = Cache(MemoryBackend(), compressor=GzipCompressor(min_size=4096))  # from 4 KiB


@cache(ttl=60)
def list_products(category: str) -> list[dict[str, str]]:
    return [{"category": category, "name": f"product {n}"} for n in range(100)]  # kilobytes of JSON


# --8<-- [end:show]
def main() -> None:
    stored = list_products("coffee")
    assert list_products("coffee") == stored
