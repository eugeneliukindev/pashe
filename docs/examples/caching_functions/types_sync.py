# --8<-- [start:show]
from dataclasses import dataclass

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec

cache = Cache(MemoryBackend(), codec=MsgspecJsonCodec())  # a codec that rebuilds dataclasses


@dataclass
class User:
    id: int
    name: str


@cache(ttl=600, key="user:{user_id}")
def get_user(user_id: int) -> User:  # the annotation is what a stored result decodes as
    return User(id=user_id, name="Ann")


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    user = get_user(1)  # User(id=1, name='Ann'): a type checker sees a User too
    cached = get_user(1)  # decoded from the backend: a User again, not a dict
    # --8<-- [end:calls]
    del user, cached
