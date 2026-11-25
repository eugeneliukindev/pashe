# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


class Token(TypedDict):
    value: str
    expires_in: int


@cache(ttl=lambda token: token["expires_in"] - 60)
def get_token() -> Token:

    # --8<-- [end:show]
    return Token(value="secret", expires_in=3600)  # what the auth server gives
