# ruff: noqa: ARG001 - a handler of Starlette takes the request whether it reads it or not
# --8<-- [start:show]
import tempfile
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pashe import AsyncRateLimiter
from pashe.asgi import RateLimitMiddleware
from pashe.backends import AsyncSQLiteBackend
from pashe.ratelimit import SlidingWindow

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = AsyncRateLimiter(backend)


def client(scope: MutableMapping[str, Any]) -> str:
    headers: dict[bytes, bytes] = dict(scope["headers"])
    return headers[b"x-forwarded-for"].decode().split(",")[0]  # as your proxy sets it


async def search(request: Request) -> JSONResponse:
    return JSONResponse([{"id": 1}])


app = Starlette(
    routes=[Route("/search", search)],
    middleware=[Middleware(RateLimitMiddleware, limiter=limiter, limit=SlidingWindow.per_minute(100), key=client)],
)
# --8<-- [end:show]
