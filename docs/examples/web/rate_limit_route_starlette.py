# ruff: noqa: ARG001 - a handler of Starlette takes the request whether it reads it or not
# --8<-- [start:show]
from collections.abc import MutableMapping
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from pashe import AsyncRateLimiter
from pashe.asgi import RateLimitMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.ratelimit import FixedWindow

limiter = AsyncRateLimiter(AsyncMemoryBackend())


def client(scope: MutableMapping[str, Any]) -> str:
    headers: dict[bytes, bytes] = dict(scope["headers"])
    return headers[b"x-forwarded-for"].decode().split(",")[0]  # as your proxy sets it


logins = FixedWindow(calls=5, per=60, ban_for=300)


async def catalog(request: Request) -> JSONResponse:
    return JSONResponse(["kettle"])


async def login(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


app = Starlette(
    routes=[
        Route("/catalog", catalog),
        Route("/login", login, middleware=[Middleware(RateLimitMiddleware, limiter=limiter, limit=logins, key=client)]),
    ],
)
# --8<-- [end:show]
