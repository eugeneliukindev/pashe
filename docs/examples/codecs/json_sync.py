# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())  # JsonCodec is the default


class User(TypedDict):
    id: int
    name: str


@cache(ttl=60)
def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")  # comes back as a dict


# --8<-- [end:show]
def main() -> None:
    assert get_user(1) == get_user(1)
