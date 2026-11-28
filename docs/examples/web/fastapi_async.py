# ruff: noqa: ARG001 - a handler takes the request whether it reads it or not
# --8<-- [start:show]
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from pashe import AsyncCache, AsyncRateLimiter
from pashe.asgi import CacheHeadersMiddleware
from pashe.backends import AsyncSQLiteBackend
from pashe.contrib.fastapi import rate_limit
from pashe.errors import OverloadedError, RateLimitedError
from pashe.hooks import CacheHeadersHook
from pashe.ratelimit import SlidingWindow

headers = CacheHeadersHook()
backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
cache = AsyncCache(backend, hooks=[headers])
limiter = AsyncRateLimiter(backend)

app = FastAPI()
app.add_middleware(CacheHeadersMiddleware, hook=headers)


@dataclass
class Result:
    id: int


@app.exception_handler(RateLimitedError)
async def rate_limited(request: Request, error: RateLimitedError) -> JSONResponse:
    retry_after = str(math.ceil(error.retry_after))  # whole seconds, rounded up: not back too early
    headers = {"Retry-After": retry_after}
    return JSONResponse({"detail": str(error)}, status_code=429, headers=headers)


@app.exception_handler(OverloadedError)
async def overloaded(request: Request, error: OverloadedError) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=503)


def client_key(request: Request) -> str:
    return request.headers["x-forwarded-for"].split(",")[0]


@app.get("/search", dependencies=[Depends(rate_limit(limiter, SlidingWindow.per_minute(100), key=client_key))])
async def search(query: str) -> list[Result]:
    return [Result(id=1)]


# --8<-- [end:show]
