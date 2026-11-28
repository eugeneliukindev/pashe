from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend(), prefix="app:")  # Redis on the page; memory here, so the test runs it


# --8<-- [start:function]
async def load_user(user_id: int) -> dict[str, str]:
    return {"id": str(user_id), "name": "Ann"}  # your query to the database


@cache(ttl=300, key="user:{user_id}")
async def get_user(user_id: int) -> dict[str, str]:
    return await load_user(user_id)


# --8<-- [end:function]
async def main() -> None:
    # --8<-- [start:calls]
    await get_user(1)
    await get_user(1)
    # --8<-- [end:calls]

    # --8<-- [start:methods]
    user = {"id": "1", "name": "Ada"}
    await get_user.refresh(1)  # reload and store, whatever is stored
    await get_user.set(user, 1)  # store a value as the result of get_user(1), as right after saving it
    await get_user.invalidate(1)  # drop the stored result
    # --8<-- [end:methods]
