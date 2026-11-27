# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


class User(TypedDict):
    id: int


async def load_users(user_ids: list[int]) -> dict[int, User]:
    return {user_id: User(id=user_id) for user_id in user_ids}


@cache.batch(ttl=300, key="user:{}")  # each item under a key of its own
async def get_users(user_ids: list[int]) -> dict[int, User]:
    return await load_users(user_ids)


# --8<-- [end:show]
async def main() -> None:
    # --8<-- [start:calls]
    await get_users([1, 2, 3])  # loads the three
    await get_users([2, 3, 4])  # loads only 4
    await get_users.invalidate(2)
    await get_users.invalidate(3)
    await get_users([2, 3])  # loads both again
    # --8<-- [end:calls]
