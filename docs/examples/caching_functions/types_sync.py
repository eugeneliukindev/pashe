# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int
    name: str


@cache(ttl=600, key="user:{user_id}")
def get_user(user_id: int) -> User:  # the annotation is what a stored result decodes as
    return User(id=user_id, name="Ann")


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    user = get_user(1)  # {'id': 1, 'name': 'Ann'}: a type checker sees a User
    cached = get_user(1)  # decoded from the backend as a User: the same dict
    # --8<-- [end:calls]
    del user, cached
