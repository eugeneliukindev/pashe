# --8<-- [start:imports]
from typing import TypedDict

from redis import Redis

from pashe import Cache
from pashe.contrib.redis import RedisBackend
from pashe.options import Stale

# --8<-- [end:imports]

# --8<-- [start:show]
cache = Cache(RedisBackend(Redis.from_url("redis://localhost:6379/0")), prefix="users:")


class User(TypedDict):
    id: int


def load_user_from_the_database(user_id: int) -> User:
    return User(id=user_id)  # your query to the database


@cache(ttl=300, tags=["users"], stale=Stale(while_revalidate=30))
def get_user(user_id: int) -> User:
    return load_user_from_the_database(user_id)


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_user(1)  # loads and stores
    get_user(1)  # answered from Redis
    cache.invalidate_tags("users")  # every entry tagged "users" is a miss now
    # --8<-- [end:calls]
