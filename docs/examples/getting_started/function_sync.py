from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend(), prefix="app:")  # Redis on the page; memory here, so the test runs it


# --8<-- [start:function]
def load_user(user_id: int) -> dict[str, str]:
    return {"id": str(user_id), "name": "Ann"}  # your query to the database


@cache(ttl=300, key="user:{user_id}")
def get_user(user_id: int) -> dict[str, str]:
    return load_user(user_id)


# --8<-- [end:function]
def main() -> None:
    # --8<-- [start:calls]
    get_user(1)  # loads, stores and returns
    get_user(1)  # returns the stored result
    # --8<-- [end:calls]

    # --8<-- [start:methods]
    user = {"id": "1", "name": "Ada"}
    get_user.refresh(1)  # reload and store, whatever is stored
    get_user.set(user, 1)  # store a value as the result of get_user(1), as right after saving it
    get_user.invalidate(1)  # drop the stored result
    # --8<-- [end:methods]
