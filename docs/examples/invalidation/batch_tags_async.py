# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


@cache(ttl=600, tags=["user:{user_id}"])
async def get_user(user_id: int) -> dict[str, int]:
    return {"id": user_id}


@cache.batch(ttl=600, key="user:{}", tags=["user:{}"])  # the tag of each item, as of get_user
async def get_users(user_ids: list[int]) -> dict[int, dict[str, int]]:
    return {user_id: {"id": user_id} for user_id in user_ids}


async def on_user_changed(user_id: int) -> None:
    await cache.invalidate_tags(f"user:{user_id}")  # get_user(3) and item 3 of get_users([...]) reload


# --8<-- [end:show]
async def main() -> None:
    await get_user(3)
    await get_users([3, 4])
    await on_user_changed(3)
