# --8<-- [start:show]
from dataclasses import dataclass

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec

cache = AsyncCache(AsyncMemoryBackend(), codec=MsgspecJsonCodec())  # it stores a dataclass


@dataclass
class User:
    id: int


async def load_users(user_ids: list[int]) -> dict[int, User]:
    return {user_id: User(user_id) for user_id in user_ids}


@cache.batch(ttl=300, key="user:{}")
async def get_users(user_ids: list[int]) -> dict[int, User]:
    return await load_users(user_ids)


# --8<-- [end:show]
async def main() -> None:
    # --8<-- [start:calls]
    await get_users([1, 2, 3])  # loads the three
    await get_users([2, 3, 4])  # loads only 4
    await get_users.invalidate(2)
    # --8<-- [end:calls]
