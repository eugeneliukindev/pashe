# --8<-- [start:show]
from typing import TypedDict

from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.contrib.redis import AsyncRedisBackend

cache = AsyncCache(AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0")), prefix="app:")


class User(TypedDict):
    id: int
    name: str


names = {1: "Ann"}  # your database


async def save_name(user_id: int, name: str) -> None:
    names[user_id] = name


@cache(ttl=300, tags=["user:{user_id}"])
async def get_user(user_id: int) -> User:
    return User(id=user_id, name=names[user_id])


async def rename(user_id: int, name: str) -> None:
    await save_name(user_id, name)
    await cache.invalidate_tags(f"user:{user_id}")


# --8<-- [end:show]
