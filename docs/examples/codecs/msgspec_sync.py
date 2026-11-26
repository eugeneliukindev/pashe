# --8<-- [start:show]
from dataclasses import dataclass

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.msgspec import MsgspecMsgpackCodec

cache = Cache(MemoryBackend(), codec=MsgspecMsgpackCodec())  # MsgspecJsonCodec when others read it


@dataclass
class User:
    id: int
    name: str


@cache(ttl=60)
def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")  # comes back as a User


# --8<-- [end:show]
def main() -> None:
    assert isinstance(get_user(1), User)
    assert get_user(1) == User(id=1, name="Ada")
