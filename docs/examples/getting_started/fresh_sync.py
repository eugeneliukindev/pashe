# --8<-- [start:show]
from typing import TypedDict

from redis import Redis

from pashe import Cache
from pashe.contrib.redis import RedisBackend

cache = Cache(RedisBackend(Redis.from_url("redis://localhost:6379/0")), prefix="app:")


class User(TypedDict):
    id: int
    name: str


names = {1: "Ann"}  # your database


def save_name(user_id: int, name: str) -> None:
    names[user_id] = name


@cache(ttl=300, tags=["user:{user_id}"])
def get_user(user_id: int) -> User:
    return User(id=user_id, name=names[user_id])


def rename(user_id: int, name: str) -> None:
    save_name(user_id, name)
    cache.invalidate_tags(f"user:{user_id}")


# --8<-- [end:show]
