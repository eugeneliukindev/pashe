# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


@cache(ttl=600, tags=["users", "user:{user_id}", "team:{team_id}"])
async def get_member(user_id: int, team_id: int) -> dict[str, int]:
    return {"user": user_id, "team": team_id}


async def main() -> None:
    await get_member(1, team_id=7)
    await get_member(2, team_id=7)

    await cache.invalidate_tags("user:1")  # get_member(1, ...) loads again, get_member(2, ...) does not
    await cache.invalidate_tags("team:7")  # both load again
    await cache.invalidate_tags("users")  # every result of every member loads again


# --8<-- [end:show]
