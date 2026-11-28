# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache(ttl=60)
def get_user(user_id: int) -> dict[str, str]:
    return {"id": str(user_id)}


user = {"id": "1", "name": "Ann"}


def main() -> None:
    get_user(1)  # the stored result, or load, store and return
    get_user.get(1)  # the fresh stored result, or None: it loads nothing
    get_user.refresh(1)  # load and store whatever is stored; an error of the function leaves the entry alone
    get_user.set(user, 1)  # store user as the result of get_user(1)
    get_user.invalidate(1)  # drop the stored result; True if there was one
    # --8<-- [end:show]
