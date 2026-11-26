# --8<-- [start:show]
from dataclasses import dataclass

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec

cache = Cache(MemoryBackend(), codec=MsgspecJsonCodec())  # it stores a dataclass


@dataclass
class User:
    id: int


def load_users(user_ids: list[int]) -> dict[int, User]:
    return {user_id: User(user_id) for user_id in user_ids}


@cache.batch(ttl=300, key="user:{}", tags=["user:{}"])  # the tag of each item, as of get_user
def get_users(user_ids: list[int]) -> dict[int, User]:
    return load_users(user_ids)


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    get_users([1, 2, 3])  # loads the three
    get_users([2, 3, 4])  # loads only 4
    get_users.invalidate(2)
    cache.invalidate_tags("user:3")
    get_users([2, 3])  # loads both again
    # --8<-- [end:calls]
