"""RateLimitMiddleware of pashe.asgi over Starlette and Litestar, and CacheHeadersMiddleware under Litestar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest
from litestar import Litestar, get
from litestar.middleware import DefineMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from pashe import AsyncCache
from pashe.asgi import CacheHeadersMiddleware, RateLimitMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.hooks import CacheHeadersHook
from pashe.ratelimit import FixedWindow
from tests.harness.helpers import AsyncFailingMemoryBackend

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.requests import Request

_LIMIT = FixedWindow(calls=2, per=60)


def _client(_scope: MutableMapping[str, Any]) -> str:
    return "client"


def _starlette(cache: AsyncCache, reached: list[str]) -> Starlette:
    async def search(_request: Request) -> PlainTextResponse:
        reached.append("search")
        return PlainTextResponse("found")

    limited = [Middleware(RateLimitMiddleware, cache=cache, limit=_LIMIT, key=_client)]
    return Starlette(routes=[Route("/search", search, middleware=limited)])


async def test_a_request_over_the_limit_is_answered_429_and_never_reaches_the_route() -> None:
    reached: list[str] = []
    app = _starlette(AsyncCache(AsyncMemoryBackend()), reached)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        first = await http.get("/search")
        await http.get("/search")

        refused = await http.get("/search")

    assert (first.status_code, first.headers["ratelimit-limit"], first.headers["ratelimit-remaining"]) == (
        200,
        "2",
        "1",
    )
    assert (refused.status_code, refused.text) == (429, "Too Many Requests")
    assert int(refused.headers["retry-after"]) > 0
    assert reached == ["search", "search"]


async def test_a_backend_that_fails_lets_the_request_through_uncounted() -> None:
    backend = AsyncFailingMemoryBackend()
    backend.down = True
    app = _starlette(AsyncCache(backend), [])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/search")

    assert response.status_code == 200
    assert "ratelimit-limit" not in response.headers


async def test_a_route_of_litestar_takes_the_rate_limit() -> None:
    cache = AsyncCache(AsyncMemoryBackend())

    limited = DefineMiddleware(RateLimitMiddleware, cache=cache, limit=_LIMIT, key=_client)  # type: ignore[arg-type]  # Litestar types ASGI with TypedDicts, Starlette and pashe with mappings

    @get("/search", middleware=[limited])
    async def search() -> str:
        return "found"

    app = Litestar(route_handlers=[search])
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]  # as above: httpx types ASGI as Starlette does
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        statuses = [(await http.get("/search")).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


async def test_litestar_takes_the_cache_headers_middleware() -> None:
    headers = CacheHeadersHook()
    cache = AsyncCache(AsyncMemoryBackend(), hooks=[headers])

    @cache(ttl=60, key="report")
    async def get_report() -> str:
        return "ready"

    @get("/report")
    async def report() -> str:
        return await get_report()

    told = DefineMiddleware(CacheHeadersMiddleware, hook=headers)  # type: ignore[arg-type]  # Litestar types ASGI with TypedDicts, Starlette and pashe with mappings
    app = Litestar(route_handlers=[report], middleware=[told])
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]  # as above: httpx types ASGI as Starlette does
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get("/report")

    assert response.headers["cache-status"].startswith("pashe; fwd=miss")


def test_a_cost_over_the_limit_is_refused_when_it_is_made() -> None:
    with pytest.raises(ValueError, match="cost is 3"):
        RateLimitMiddleware(_client, cache=AsyncCache(AsyncMemoryBackend()), limit=_LIMIT, key=_client, cost=3)  # type: ignore[arg-type]  # any function is an app here
