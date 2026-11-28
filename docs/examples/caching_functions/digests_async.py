# ruff: noqa: ARG001, S106 - as the page shows it: a body that ignores its argument, a secret inline
# --8<-- [start:show]
import dataclasses

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend(), key_secret="a secret of sixteen bytes or more")


@dataclasses.dataclass
class Filters:
    category: str
    colors: set[str]


@cache(ttl=60, key="search:{filters:blake2b}")
async def search(filters: Filters) -> list[int]:
    return [1, 2, 3]


@cache(ttl=300, key="user:{email:hmac}")
async def get_user(email: str) -> dict[str, str]:
    return {"email": email}


# --8<-- [end:show]
async def main() -> None:
    # --8<-- [start:calls]
    await search(Filters("coffee", {"red", "blue"}))
    await get_user("ada@example.com")
    cache.key_for("user:{email:hmac}", email="ada@example.com")  # the key of that call, to find it
    # --8<-- [end:calls]
