# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int


@cache(
    ttl=300,  # fresh for 5 minutes
    key="user:{user_id}",  # get_user(1) is under "user:1"
)
def get_user(user_id: int) -> User:  # a stored value decodes as User
    return User(id=user_id)  # your query to the database


# --8<-- [end:show]
