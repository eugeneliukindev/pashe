# --8<-- [start:show]
from dataclasses import dataclass

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.msgspec import MsgspecMsgpackCodec

cache = AsyncCache(AsyncMemoryBackend(), codec=MsgspecMsgpackCodec())  # MsgspecJsonCodec when others read it


@dataclass
class User:
    id: int
    name: str


@cache(ttl=60)
async def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")  # comes back as a User


# --8<-- [end:show]
async def main() -> None:
    assert isinstance(await get_user(1), User)
    assert await get_user(1) == User(id=1, name="Ada")
