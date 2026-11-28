# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Negative

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int


class UserNotFoundError(LookupError):
    pass


users = {1: User(id=1)}  # your database


@cache(ttl=300, negative=Negative(on=(UserNotFoundError,), ttl=30))
def get_user(user_id: int) -> User:
    user = users.get(user_id)
    if user is None:
        raise UserNotFoundError(user_id)  # kept as the answer for 30 s
    return user


# --8<-- [end:show]
