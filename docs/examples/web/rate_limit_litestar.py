# --8<-- [start:show]
from collections.abc import MutableMapping
from typing import Any

from litestar import Litestar, get
from litestar.middleware import DefineMiddleware

from pashe import AsyncCache
from pashe.asgi import RateLimitMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import FixedWindow

cache = AsyncCache(AsyncMemoryBackend())


def client(scope: MutableMapping[str, Any]) -> str:
    headers: dict[bytes, bytes] = dict(scope["headers"])
    return headers[b"x-forwarded-for"].decode().split(",")[0]  # as your proxy sets it


limit = FixedWindow(calls=5, per=60, ban_for=300)
logins = DefineMiddleware(RateLimitMiddleware, cache=cache, limit=limit, key=client)  # type: ignore[arg-type]  # Litestar types ASGI with TypedDicts, Starlette and pashe with mappings


@get("/catalog")
async def catalog() -> list[str]:
    return ["kettle"]


@get("/login", middleware=[logins])  # this route alone
async def login() -> str:
    return "ok"


app = Litestar(route_handlers=[catalog, login])
# --8<-- [end:show]
