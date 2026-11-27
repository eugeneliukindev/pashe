# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stale

backend = MemoryBackend()
cache = Cache(backend, prefix="shop:")


class User(TypedDict):
    id: int
    name: str


@cache(ttl=300, key="user:{user_id}", tags=["users"], stale=Stale(while_revalidate=60))
def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")


# --8<-- [end:show]
def main() -> None:
    get_user(1)
