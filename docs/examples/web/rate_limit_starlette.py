# ruff: noqa: ARG001 - a handler of Starlette takes the request whether it reads it or not
# --8<-- [start:show]
from collections.abc import MutableMapping
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pashe import AsyncCache
from pashe.asgi import RateLimitMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import per_minute

cache = AsyncCache(AsyncMemoryBackend())


def client(scope: MutableMapping[str, Any]) -> str:
    headers: dict[bytes, bytes] = dict(scope["headers"])
    return headers[b"x-forwarded-for"].decode().split(",")[0]  # as your proxy sets it


async def search(request: Request) -> JSONResponse:
    return JSONResponse([{"id": 1}])


app = Starlette(
    routes=[Route("/search", search)],
    middleware=[Middleware(RateLimitMiddleware, cache=cache, limit=per_minute(100), key=client)],
)
# --8<-- [end:show]
