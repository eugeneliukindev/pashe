import tempfile
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from pashe import AsyncRateLimiter
from pashe.asgi import RateLimitMiddleware
from pashe.backends import AsyncSQLiteBackend
from pashe.ratelimit import SlidingWindow

backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "my-app-cache.db")  # every process of the machine
limiter = AsyncRateLimiter(backend)


def client(scope: MutableMapping[str, Any]) -> str:
    headers: dict[bytes, bytes] = dict(scope["headers"])
    return headers[b"x-forwarded-for"].decode().split(",")[0]  # as your proxy sets it


app = FastAPI()
app.add_middleware(RateLimitMiddleware, limiter=limiter, limit=SlidingWindow.per_minute(100), key=client)


@app.get("/search")
async def search() -> list[dict[str, int]]:
    return [{"id": 1}]
