# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())
names = {1: "Ann"}  # the database of the page


@cache(ttl=600, tags=["user:{user_id}"])
async def get_user(user_id: int) -> dict[str, str]:
    return {"name": names[user_id]}


@cache.invalidates(tags=["user:{user_id}"])  # after every call, even one that raised
async def rename_user(user_id: int, name: str) -> None:
    names[user_id] = name


# --8<-- [end:show]
