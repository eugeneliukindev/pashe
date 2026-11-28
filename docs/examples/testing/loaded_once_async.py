# --8<-- [start:show]
from pashe import AsyncCache, AsyncCachedFunction
from pashe.backends import AsyncMemoryBackend

loads: list[int] = []


def make_get_user(cache: AsyncCache) -> AsyncCachedFunction[[int], dict[str, int]]:
    @cache(ttl=300, key="user:{user_id}")
    async def get_user(user_id: int) -> dict[str, int]:
        loads.append(user_id)
        return {"id": user_id}

    return get_user


async def test_a_user_is_loaded_once() -> None:  # with pytest-asyncio or anyio
    get_user = make_get_user(AsyncCache(AsyncMemoryBackend()))
    await get_user(1)
    await get_user(1)
    assert loads == [1]


# --8<-- [end:show]
