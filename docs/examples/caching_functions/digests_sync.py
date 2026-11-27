# ruff: noqa: ARG001, S106 - as the page shows it: a body that ignores its argument, a secret inline
# --8<-- [start:show]
import dataclasses

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend(), key_secret="a secret of sixteen bytes or more")


@dataclasses.dataclass
class Filters:
    category: str
    colors: set[str]


@cache(ttl=60, key="search:{filters:blake2b}")
def search(filters: Filters) -> list[int]:
    return [1, 2, 3]


@cache(ttl=300, key="user:{email:hmac}")
def get_user(email: str) -> dict[str, str]:
    return {"email": email}


# --8<-- [end:show]
def main() -> None:
    # --8<-- [start:calls]
    search(Filters("coffee", {"red", "blue"}))
    get_user("ada@example.com")
    cache.key_for("user:{email:hmac}", email="ada@example.com")  # the key of that call, to find it
    # --8<-- [end:calls]
