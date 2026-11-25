# --8<-- [start:show]
from dataclasses import dataclass

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec

cache = AsyncCache(AsyncMemoryBackend(), codec=MsgspecJsonCodec())  # a codec that rebuilds dataclasses


@dataclass
class User:
    id: int
    name: str


@cache(ttl=600, key="user:{user_id}")
async def get_user(user_id: int) -> User:  # the annotation is what a stored result decodes as
    return User(id=user_id, name="Ann")


# --8<-- [end:show]
async def main() -> None:
    # --8<-- [start:calls]
    user = await get_user(1)  # User(id=1, name='Ann'): a type checker sees a User too
    cached = await get_user(1)  # decoded from the backend: a User again, not a dict
    # --8<-- [end:calls]
    del user, cached
