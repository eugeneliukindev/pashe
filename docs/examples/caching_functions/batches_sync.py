# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int


def load_users(user_ids: list[int]) -> dict[int, User]:
    return {user_id: User(id=user_id) for user_id in user_ids}


@cache.batch(ttl=300, key="user:{}")  # each item under a key of its own
def get_users(user_ids: list[int]) -> dict[int, User]:
    return load_users(user_ids)


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_users([1, 2, 3])  # loads the three
    get_users([2, 3, 4])  # loads only 4
    get_users.invalidate(2)
    get_users.invalidate(3)
    get_users([2, 3])  # loads both again
    # --8<-- [end:calls]
