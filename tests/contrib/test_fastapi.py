"""The ASGI middleware and the FastAPI helpers over a live FastAPI application."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import httpx
import pytest
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from pashe import AsyncCache, AsyncRateLimiter, Cache
from pashe.asgi import CacheHeadersMiddleware
from pashe.backends import AsyncMemoryBackend, MemoryBackend
from pashe.contrib.fastapi import rate_limit
from pashe.errors import InvalidOptionsError, OverloadedError, RateLimitedError
from pashe.hooks import CacheHeadersHook
from pashe.ratelimit import FixedWindow
from tests.harness.helpers import Source

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from pashe.asgi import Message, Receive, Scope, Send
    from tests.harness.helpers import Clock


def _app(clock: Clock) -> FastAPI:  # noqa: C901 - one endpoint per case under test
    headers = CacheHeadersHook()
    cache = AsyncCache(AsyncMemoryBackend(), hooks=[headers], clock=clock)
    sync_cache = Cache(MemoryBackend(), hooks=[headers], clock=clock)
    limiter = AsyncRateLimiter(AsyncMemoryBackend(), clock=clock)
    app = FastAPI()
    app.add_middleware(CacheHeadersMiddleware, hook=headers)

    @app.exception_handler(RateLimitedError)
    async def rate_limited(_: Request, error: RateLimitedError) -> JSONResponse:  # as the web guide shows
        retry_after = str(math.ceil(error.retry_after))
        return JSONResponse({"detail": str(error)}, status_code=429, headers={"Retry-After": retry_after})

    @app.exception_handler(OverloadedError)
    async def overloaded(_: Request, error: OverloadedError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=503)

    @cache(ttl=60, key="user:{user_id}")
    async def get_user(user_id: int) -> dict[str, int]:
        return {"id": user_id}

    @cache(ttl=10, key="plan")
    async def get_plan() -> str:
        return "pro"

    @sync_cache(ttl=30, key="report")
    def get_report() -> str:
        return "ready"

    @app.get("/users/{user_id}")
    async def user(user_id: int) -> dict[str, int]:
        return await get_user(user_id)

    @app.get("/profile")
    async def profile() -> dict[str, object]:
        return {"user": await get_user(1), "plan": await get_plan()}

    @app.get("/report")
    def report() -> str:  # a def endpoint runs in a thread of FastAPI
        return get_report()

    @app.get("/plain")
    async def plain() -> dict[str, bool]:
        return {"plain": True}

    @app.get("/own")
    async def own(response: Response) -> dict[str, int]:
        response.headers["Cache-Control"] = "no-store"
        return await get_user(2)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"a"
            yield b"b"

        return StreamingResponse(chunks())

    @app.get("/busy")
    async def busy() -> None:
        raise OverloadedError

    @app.get(
        "/limited", dependencies=[Depends(rate_limit(limiter, FixedWindow(calls=2, per=60), key=lambda _: "client"))]
    )
    async def limited() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/users/{user_id}")
    async def update(user_id: int) -> dict[str, int]:
        return await get_user(user_id)

    return app


@pytest.fixture
async def client(clock: Clock) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(clock)), base_url="http://test") as http:
        yield http


async def test_a_cached_response_says_how_long_it_stays_fresh(client: httpx.AsyncClient) -> None:
    first = await client.get("/users/1")
    assert first.json() == {"id": 1}
    assert first.headers["cache-control"] == "private, max-age=60"
    assert first.headers["cache-status"] == "pashe; fwd=miss; ttl=60"
    second = await client.get("/users/1")
    assert second.headers["cache-status"] == "pashe; hit; ttl=60"
    assert second.headers["etag"] == first.headers["etag"]


async def test_an_unchanged_response_is_answered_304(client: httpx.AsyncClient) -> None:
    tag = (await client.get("/users/1")).headers["etag"]
    unchanged = await client.get("/users/1", headers={"If-None-Match": f"W/{tag}"})
    assert unchanged.status_code == 304
    assert not unchanged.content
    assert unchanged.headers["etag"] == tag
    assert "content-length" not in unchanged.headers
    other = await client.get("/users/2", headers={"If-None-Match": tag})
    assert other.status_code == 200


async def test_the_shortest_lived_result_bounds_the_response(client: httpx.AsyncClient) -> None:
    response = await client.get("/profile")
    assert response.headers["cache-control"] == "private, max-age=10"


async def test_the_calls_of_a_def_endpoint_count(client: httpx.AsyncClient) -> None:
    response = await client.get("/report")
    assert response.headers["cache-control"] == "private, max-age=30"


async def test_a_response_without_cached_calls_gets_only_an_etag(client: httpx.AsyncClient) -> None:
    response = await client.get("/plain")
    assert response.headers["etag"]
    assert "cache-control" not in response.headers
    assert "cache-status" not in response.headers


async def test_the_cache_control_of_the_endpoint_wins(client: httpx.AsyncClient) -> None:
    response = await client.get("/own")
    assert response.headers["cache-control"] == "no-store"


async def test_a_streamed_response_passes_as_it_is(client: httpx.AsyncClient) -> None:
    response = await client.get("/stream")
    assert response.content == b"ab"
    assert "etag" not in response.headers


async def test_only_get_is_touched(client: httpx.AsyncClient) -> None:
    response = await client.post("/users/1")
    assert response.json() == {"id": 1}
    assert "etag" not in response.headers


async def test_rate_limit_tells_what_is_left_and_refuses_past_it(client: httpx.AsyncClient) -> None:
    first = await client.get("/limited")
    assert (first.headers["ratelimit-limit"], first.headers["ratelimit-remaining"]) == ("2", "1")
    assert first.headers["ratelimit-reset"] == "60"
    await client.get("/limited")
    refused = await client.get("/limited")
    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "60"
    assert "rate limited" in refused.json()["detail"]


async def test_an_overloaded_load_is_503(client: httpx.AsyncClient) -> None:
    response = await client.get("/busy")
    assert response.status_code == 503
    assert response.json() == {"detail": "every load slot is taken"}


async def test_the_response_goes_before_the_work_after_it() -> None:
    sent: list[str] = []

    async def app(
        _scope: Scope,
        _receive: Receive,
        send: Send,
    ) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
        sent.append("background task")  # what Starlette runs after the body

    async def send(message: Message) -> None:
        sent.append(message["type"])

    scope = {"type": "http", "method": "GET", "headers": []}
    await CacheHeadersMiddleware(app, hook=CacheHeadersHook())(scope, _nothing, send)
    assert sent == ["http.response.start", "http.response.body", "background task"]


async def _nothing() -> Message:
    return {"type": "http.disconnect"}


def test_a_rate_limit_that_costs_more_than_its_limit_is_refused_when_it_is_made() -> None:
    limiter = AsyncRateLimiter(AsyncMemoryBackend())

    with pytest.raises(InvalidOptionsError, match="cost is 10: a call must cost from 1 to the 5 calls"):
        rate_limit(limiter, FixedWindow(calls=5, per=60), key=lambda _request: "ip", cost=10)


def _reloading_app(
    source: Source,
    clock: Clock,
    *,
    allow: Callable[[Scope], bool] | None,
) -> FastAPI:
    headers = CacheHeadersHook()
    cache = AsyncCache(AsyncMemoryBackend(), hooks=[headers], clock=clock)

    @cache(ttl=60, key="user:{user_id}")
    async def get_user(user_id: int) -> dict[str, int]:
        return source(user_id)

    app = FastAPI()
    app.add_middleware(CacheHeadersMiddleware, hook=headers, honor_no_cache=allow)

    @app.get("/users/{user_id}")
    async def user(user_id: int) -> dict[str, int]:
        return await get_user(user_id)

    return app


def _staff(scope: Scope) -> bool:
    return (b"x-role", b"staff") in scope["headers"]


@pytest.mark.parametrize(
    ("allow", "asked", "loads", "status"),
    [
        (_staff, {}, 1, "pashe; hit; ttl=60"),
        (None, {"Cache-Control": "no-cache"}, 1, "pashe; hit; ttl=60"),
        (_staff, {"Cache-Control": "no-cache"}, 1, "pashe; hit; ttl=60"),
        (_staff, {"Cache-Control": "no-cache", "X-Role": "staff"}, 2, "pashe; fwd=request; ttl=60"),
        (_staff, {"Pragma": "no-cache", "X-Role": "staff"}, 2, "pashe; fwd=request; ttl=60"),
        (_staff, {"Cache-Control": "max-age=0", "X-Role": "staff"}, 1, "pashe; hit; ttl=60"),
    ],
    ids=["no header", "nobody allowed", "not allowed", "allowed", "pragma", "a plain reload"],
)
async def test_a_request_with_no_cache_reloads_its_results_only_if_it_is_allowed(
    allow: Callable[[Scope], bool] | None,
    asked: dict[str, str],
    loads: int,
    status: str,
    clock: Clock,
) -> None:
    source = Source()
    app = _reloading_app(source, clock, allow=allow)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await http.get("/users/1")

        response = await http.get("/users/1", headers=asked)

    assert source.calls == loads
    assert response.headers["cache-status"] == status


async def test_no_cache_in_one_of_two_lines_of_cache_control_counts(clock: Clock) -> None:
    source = Source()
    app = _reloading_app(source, clock, allow=_staff)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await http.get("/users/1")

        await http.get(
            "/users/1", headers=[("Cache-Control", "max-age=0"), ("Cache-Control", "no-cache"), ("X-Role", "staff")]
        )

    assert source.calls == 2  # the lines are joined, as a WSGI server joins them
