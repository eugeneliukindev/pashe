# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Stampede

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int


@cache(
    ttl=300,  # (1)!
    key="user:{user_id}",  # (2)!
    tags=["users"],  # (3)!
    stampede=Stampede(jitter=0.1),  # (4)!
)
def get_user(user_id: int) -> User:  # (5)!
    return User(id=user_id)  # your query to the database


# --8<-- [end:show]
