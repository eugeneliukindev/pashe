# --8<-- [start:show]
from pydantic import BaseModel

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.pydantic import PydanticCodec

cache = Cache(MemoryBackend(), codec=PydanticCodec())


class User(BaseModel):
    id: int
    name: str


@cache(ttl=60)
def get_user(user_id: int) -> User:
    return User(id=user_id, name="Ada")  # comes back as a User, validated


# --8<-- [end:show]
def main() -> None:
    get_user(1)
    assert get_user(1) == User(id=1, name="Ada")
