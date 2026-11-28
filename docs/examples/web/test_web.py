from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from types import ModuleType


_ADDRESS = "http://localhost:8000"
_CLIENT = {"X-Forwarded-For": "203.0.113.7"}


async def test_the_headers_of_a_cached_call_are_those_the_page_shows() -> None:
    transport = httpx.ASGITransport(app=_page("headers_fastapi").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        first = await client.get("/products/1")
        second = await client.get("/products/1")

        unchanged = await client.get("/products/1", headers={"If-None-Match": second.headers["etag"]})

    assert first.headers["cache-status"].startswith("pashe; fwd=miss; ttl=")
    assert first.headers["cache-control"].startswith("private, max-age=")
    assert second.headers["cache-status"].startswith("pashe; hit; ttl=")
    assert (unchanged.status_code, unchanged.content) == (304, b"")


async def test_a_rate_limit_tells_what_is_left_then_refuses() -> None:
    transport = httpx.ASGITransport(app=_page("fastapi_async").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        first = await client.get("/search", params={"query": "kettle"}, headers=_CLIENT)
        for _ in range(99):
            await client.get("/search", params={"query": "kettle"}, headers=_CLIENT)

        refused = await client.get("/search", params={"query": "kettle"}, headers=_CLIENT)

    assert (first.headers["ratelimit-limit"], first.headers["ratelimit-remaining"]) == ("100", "99")
    assert refused.status_code == 429
    assert "retry-after" in refused.headers


async def test_a_cached_endpoint_runs_once_until_its_tags_are_invalidated() -> None:
    transport = httpx.ASGITransport(app=_page("endpoint_async").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        first = await client.get("/products/1", params={"lang": "ru"})
        second = await client.get("/products/1", params={"lang": "ru"})
        await _page("endpoint_async").rename(1)

        after = await client.get("/products/1", params={"lang": "ru"})

    assert first.headers["cache-status"].startswith("pashe; fwd=miss")
    assert second.headers["cache-status"].startswith("pashe; hit")
    assert second.headers["cache-control"].startswith("public, max-age=")
    assert after.headers["cache-status"].startswith("pashe; fwd=miss")


async def test_a_staff_request_with_no_cache_reloads_and_another_does_not() -> None:
    transport = httpx.ASGITransport(app=_page("no_cache_fastapi").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        await client.get("/products/1")
        client_asks = await client.get("/products/1", headers={"Cache-Control": "no-cache"})

        staff_asks = await client.get("/products/1", headers={"Cache-Control": "no-cache", "X-Role": "staff"})

    assert client_asks.headers["cache-status"].startswith("pashe; hit; ttl=")
    assert staff_asks.headers["cache-status"].startswith("pashe; fwd=request; ttl=")
    assert _page("no_cache_fastapi").loads == [1, 1]


async def test_the_whole_starlette_application_takes_the_rate_limit() -> None:
    transport = httpx.ASGITransport(app=_page("rate_limit_starlette").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        first = await client.get("/search", headers=_CLIENT)
        for _ in range(99):
            await client.get("/search", headers=_CLIENT)

        refused = await client.get("/search", headers=_CLIENT)

    assert (first.headers["ratelimit-limit"], first.headers["ratelimit-remaining"]) == ("100", "99")
    assert (refused.status_code, refused.text) == (429, "Too Many Requests")
    assert "retry-after" in refused.headers


async def test_the_whole_fastapi_application_takes_the_rate_limit() -> None:
    transport = httpx.ASGITransport(app=_page("rate_limit_fastapi").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        first = await client.get("/search", headers=_CLIENT)
        for _ in range(99):
            await client.get("/search", headers=_CLIENT)

        refused = await client.get("/search", headers=_CLIENT)

    assert (first.headers["ratelimit-limit"], first.headers["ratelimit-remaining"]) == ("100", "99")
    assert (refused.status_code, refused.text) == (429, "Too Many Requests")
    assert "retry-after" in refused.headers


async def test_one_route_of_starlette_takes_the_rate_limit() -> None:
    transport = httpx.ASGITransport(app=_page("rate_limit_route_starlette").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        logins = [(await client.get("/login", headers=_CLIENT)).status_code for _ in range(6)]
        catalog = await client.get("/catalog", headers=_CLIENT)

    assert logins == [200, 200, 200, 200, 200, 429]
    assert (catalog.status_code, "ratelimit-limit" in catalog.headers) == (200, False)


async def test_one_route_of_fastapi_takes_the_rate_limit() -> None:
    transport = httpx.ASGITransport(app=_page("rate_limit_route_fastapi").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        logins = [(await client.get("/login", headers=_CLIENT)).status_code for _ in range(6)]
        catalog = await client.get("/catalog", headers=_CLIENT)

    assert logins == [200, 200, 200, 200, 200, 429]
    assert (catalog.status_code, "ratelimit-limit" in catalog.headers) == (200, False)


async def test_one_route_of_litestar_takes_the_rate_limit() -> None:
    transport = httpx.ASGITransport(app=_page("rate_limit_litestar").app)
    async with httpx.AsyncClient(transport=transport, base_url=_ADDRESS) as client:
        logins = [(await client.get("/login", headers=_CLIENT)).status_code for _ in range(6)]
        catalog = await client.get("/catalog", headers=_CLIENT)

    assert logins == [200, 200, 200, 200, 200, 429]
    assert (catalog.status_code, "ratelimit-limit" in catalog.headers) == (200, False)


def _page(name: str) -> ModuleType:
    """The example of a page, imported in the test, so fresh_examples gives it a cache of its own."""
    return importlib.import_module(f"examples.web.{name}")
