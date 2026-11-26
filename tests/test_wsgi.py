"""The WSGI middleware over a bare WSGI application with a sync cache."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

import httpx
import pytest

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.hooks import CacheHeadersHook
from pashe.wsgi import CacheHeadersMiddleware
from tests.harness.helpers import Source

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

    from tests.harness.helpers import Clock


def _app(clock: Clock) -> CacheHeadersMiddleware:
    headers = CacheHeadersHook()
    cache = Cache(MemoryBackend(), hooks=[headers], clock=clock)

    @cache(ttl=60, key="user:{user_id}")
    def get_user(user_id: int) -> dict[str, int]:
        return {"id": user_id}

    def stream(start_response: StartResponse) -> Iterator[bytes]:
        start_response("200 OK", [("Content-Type", "text/plain")])  # when iterated, as generators do
        yield b"a"
        yield b"b"

    def application(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        if environ["PATH_INFO"] == "/stream":
            return stream(start_response)
        body = json.dumps(get_user(1)).encode()
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    return CacheHeadersMiddleware(application, hook=headers)


@pytest.fixture
def client(clock: Clock) -> Iterator[httpx.Client]:
    with httpx.Client(transport=httpx.WSGITransport(app=_app(clock)), base_url="http://test") as http:
        yield http


def test_a_cached_response_says_how_long_it_stays_fresh(client: httpx.Client) -> None:
    first = client.get("/users/1")
    assert first.json() == {"id": 1}
    assert first.headers["cache-control"] == "private, max-age=60"
    assert first.headers["cache-status"] == "pashe; fwd=miss; ttl=60"
    assert client.get("/users/1").headers["cache-status"] == "pashe; hit; ttl=60"


def test_an_unchanged_response_is_answered_304(client: httpx.Client) -> None:
    tag = client.get("/users/1").headers["etag"]
    unchanged = client.get("/users/1", headers={"If-None-Match": tag})
    assert unchanged.status_code == 304
    assert not unchanged.content
    assert unchanged.headers["etag"] == tag
    assert "content-length" not in unchanged.headers


def test_a_response_without_length_passes_as_it_is(client: httpx.Client) -> None:
    response = client.get("/stream")
    assert response.content == b"ab"
    assert "etag" not in response.headers


def test_only_get_is_touched(client: httpx.Client) -> None:
    response = client.post("/users/1")
    assert response.json() == {"id": 1}
    assert "etag" not in response.headers


def test_a_stream_closed_before_its_first_chunk_closes_the_application() -> None:
    closed: list[bool] = []

    class Body:
        def __iter__(self) -> Iterator[bytes]:
            yield b"a"

        def close(self) -> None:
            closed.append(True)

    def application(_: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return Body()

    body = CacheHeadersMiddleware(application, hook=CacheHeadersHook())(
        {"REQUEST_METHOD": "GET"}, lambda *_: lambda _: None
    )
    body.close()  # type: ignore[attr-defined]  # the server closes a body that has close, as PEP 3333 says
    assert closed == [True]


def test_a_request_with_no_cache_it_is_allowed_reloads_its_results(clock: Clock) -> None:
    headers, source = CacheHeadersHook(), Source()
    cache = Cache(MemoryBackend(), hooks=[headers], clock=clock)

    @cache(ttl=60, key="user")
    def get_user() -> dict[str, int]:
        return source(1)

    def application(_environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        body = json.dumps(get_user()).encode()
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    app = CacheHeadersMiddleware(application, hook=headers, allow_no_cache=lambda environ: "HTTP_X_ROLE" in environ)
    with httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://test") as http:
        http.get("/")

        response = http.get("/", headers={"Cache-Control": "no-cache", "X-Role": "staff"})

    assert source.calls == 2
    assert response.headers["cache-status"] == "pashe; fwd=request; ttl=60"


def _get(application: WSGIApplication, path: str = "/", **headers: str) -> tuple[list[tuple[str, str]], bytes]:
    """Run application on a GET of path as a WSGI server does; return the headers it started and the body."""
    environ: WSGIEnvironment = {
        "PATH_INFO": path,
        "SCRIPT_NAME": "",
        "QUERY_STRING": "",
        **{f"HTTP_{name}": value for name, value in headers.items()},
    }
    setup_testing_defaults(environ)
    started: list[list[tuple[str, str]]] = []
    chunks: list[bytes] = []

    def start_response(
        _status: str, sent: list[tuple[str, str]], _exc_info: object = None, /
    ) -> Callable[[bytes], object]:
        started.append(sent)
        return chunks.append  # the write of WSGI: its bytes go out in the order of the body

    body = application(environ, start_response)
    try:
        chunks.extend(body)  # a write while it iterates lands between the parts of the body, in order
        whole = b"".join(chunks)
    finally:
        getattr(body, "close", lambda: None)()
    return started[0], whole


def test_the_headers_it_adds_are_str_as_a_wsgi_server_checks(clock: Clock) -> None:
    headers, _ = _get(validator(_app(clock)), "/users/1")  # validator asserts every name is a str

    assert "etag" in dict(headers)


class _FailsAtFirst:
    """A body that fails when iterated, and tells whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        msg = "the body failed"
        raise RuntimeError(msg)

    def close(self) -> None:
        self.closed = True


def test_a_body_that_fails_is_closed() -> None:
    body = _FailsAtFirst()
    middleware = CacheHeadersMiddleware(lambda _environ, _start: body, hook=CacheHeadersHook())

    with pytest.raises(RuntimeError, match="the body failed"):
        _get(middleware)

    assert body.closed


def test_a_streamed_body_loads_past_the_stored_results_to_its_end() -> None:
    headers, source = CacheHeadersHook(), Source()
    cache = Cache(MemoryBackend(), hooks=[headers])

    @cache(ttl=60)
    def get_user(user_id: int) -> dict[str, int]:
        return source(user_id)

    get_user(1)

    def stream(_environ: WSGIEnvironment, start_response: StartResponse) -> Iterator[bytes]:
        start_response("200 OK", [("Content-Type", "text/plain")])
        for _ in range(2):
            yield json.dumps(get_user(1)).encode()

    _get(CacheHeadersMiddleware(stream, hook=headers, allow_no_cache=lambda _environ: True), CACHE_CONTROL="no-cache")

    assert source.calls == 3  # the first call, and both chunks of the request with no-cache
