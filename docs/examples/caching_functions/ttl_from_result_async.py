# --8<-- [start:show]
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


class Token(TypedDict):
    value: str
    expires_in: int


@cache(ttl=lambda token: token["expires_in"] - 60)
async def get_token() -> Token:

    # --8<-- [end:show]
    return Token(value="secret", expires_in=3600)  # what the auth server gives
