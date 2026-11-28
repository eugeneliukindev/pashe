# --8<-- [start:show]
from pydantic import BaseModel

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.pydantic import PydanticCodec

cache = AsyncCache(AsyncMemoryBackend(), codec=PydanticCodec())


class User(BaseModel):
    id: int
    name: str


@cache(ttl=60)
async def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")  # comes back as a User, validated


# --8<-- [end:show]
async def main() -> None:
    await get_user(1)
    assert await get_user(1) == User(id=1, name="Ada")
