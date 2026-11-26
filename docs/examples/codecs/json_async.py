# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())  # JsonCodec is the default


class User(TypedDict):
    id: int
    name: str


@cache(ttl=60)
async def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")  # comes back as a dict


# --8<-- [end:show]
async def main() -> None:
    assert await get_user(1) == await get_user(1)
