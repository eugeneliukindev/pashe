# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.options import Stale

backend = AsyncMemoryBackend()
cache = AsyncCache(backend, prefix="shop:")


class User(TypedDict):
    id: int
    name: str


@cache(ttl=300, key="user:{user_id}", tags=["users"], stale=Stale(while_revalidate=60))
async def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")


# --8<-- [end:show]
async def main() -> None:
    await get_user(1)
