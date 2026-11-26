# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


@cache(ttl=60)
async def get_user(user_id: int) -> dict[str, str]:
    return {"id": str(user_id)}


user = {"id": "1", "name": "Ann"}


async def main() -> None:
    await get_user(1)  # the stored result, or load, store and return
    await get_user.get(1)  # the fresh stored result, or None: it loads nothing
    await get_user.refresh(1)  # load and store whatever is stored; an error of the function leaves it alone
    await get_user.set(user, 1)  # store user as the result of get_user(1)
    await get_user.invalidate(1)  # drop the stored result; True if there was one
    # --8<-- [end:show]
