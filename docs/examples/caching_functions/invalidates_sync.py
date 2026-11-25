# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())
names = {1: "Ann"}  # the database of the page


@cache(ttl=600, tags=["user:{user_id}"])
def get_user(user_id: int) -> dict[str, str]:
    return {"name": names[user_id]}


@cache.invalidates(tags=["user:{user_id}"])  # after every call, even one that raised
def rename_user(user_id: int, name: str) -> None:
    names[user_id] = name


# --8<-- [end:show]
