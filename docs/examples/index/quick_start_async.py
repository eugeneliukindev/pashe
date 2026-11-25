# --8<-- [start:imports]
from dataclasses import dataclass

from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.contrib.redis import AsyncRedisBackend
from pashe.options import Stale

# --8<-- [end:imports]

# --8<-- [start:show]
cache = AsyncCache(AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0")), prefix="users:")


@dataclass
class User:
    id: int


async def load_user_from_the_database(user_id: int) -> User:
    return User(user_id)  # your query to the database


# --8<-- [end:show]
async def main() -> None:
    # --8<-- [start:calls]
    @cache(ttl=300, tags=["users"], stale=Stale(while_revalidate=30))
    async def get_user(user_id: int) -> User:
        return await load_user_from_the_database(user_id)

    await get_user(1)  # loads and stores
    await get_user(1)  # answered from Redis
    await cache.invalidate_tags("users")  # every entry tagged "users" is a miss now
    # --8<-- [end:calls]
