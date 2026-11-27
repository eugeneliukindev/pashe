# ruff: noqa: ARG001 - a handler takes the request whether it reads it or not
# --8<-- [start:show]
import math

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from pashe import AsyncRateLimiter
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.fastapi import rate_limit
from pashe.errors import RateLimitedError
from pashe.ratelimit import FixedWindow

limiter = AsyncRateLimiter(AsyncMemoryBackend())
logins = FixedWindow(calls=5, per=60, ban_for=300)

app = FastAPI()


@app.exception_handler(RateLimitedError)
async def rate_limited(request: Request, error: RateLimitedError) -> JSONResponse:
    headers = {"Retry-After": str(math.ceil(error.retry_after))}  # whole seconds, rounded up: not back too early
    return JSONResponse({"detail": str(error)}, status_code=429, headers=headers)


def client_key(request: Request) -> str:
    return request.headers["x-forwarded-for"].split(",")[0]  # as your proxy sets it


@app.get("/catalog")
async def catalog() -> list[str]:
    return ["kettle"]


@app.get("/login", dependencies=[Depends(rate_limit(limiter, logins, key=client_key))])  # this route alone
async def login() -> str:
    return "ok"


# --8<-- [end:show]
