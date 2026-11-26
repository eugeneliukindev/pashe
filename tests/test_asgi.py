"""The ASGI middleware over a bare ASGI application: the messages it sends on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pashe.asgi import CacheHeadersMiddleware
from pashe.hooks import CacheHeadersHook

if TYPE_CHECKING:
    from pashe.asgi import Message, Receive, Scope, Send

_SCOPE = {"type": "http", "method": "GET", "headers": []}


async def _sent(*messages: Message, request_headers: list[tuple[bytes, bytes]] | None = None) -> list[Message]:
    """Return what the middleware sends of an application that sends messages."""

    async def application(scope: Scope, receive: Receive, send: Send) -> None:  # noqa: ARG001
        for message in messages:
            await send(message)

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope = _SCOPE | {"headers": request_headers or []}
    await CacheHeadersMiddleware(application, hook=CacheHeadersHook())(scope, None, send)  # type: ignore[arg-type]  # never received
    return sent


async def test_a_file_sent_by_path_keeps_its_start() -> None:
    start = {"type": "http.response.start", "status": 200, "headers": []}
    sent = await _sent(start, {"type": "http.response.pathsend", "path": "index.html"})
    assert [message["type"] for message in sent] == ["http.response.start", "http.response.pathsend"]


async def test_an_error_passes_as_it_is() -> None:
    start = {"type": "http.response.start", "status": 404, "headers": []}
    body = {"type": "http.response.body", "body": b"no"}
    assert await _sent(start, body) == [start, body]


async def test_a_start_without_headers_gets_an_etag() -> None:
    start = {"type": "http.response.start", "status": 200}  # headers may be left out, as ASGI says
    sent = await _sent(start, {"type": "http.response.body", "body": b"hello"})

    assert sent[0]["status"] == 200
    assert b"etag" in dict(sent[0]["headers"])


async def test_if_none_match_matches_a_weak_etag_of_the_endpoint() -> None:
    start = {"type": "http.response.start", "status": 200, "headers": [(b"etag", b'W/"v1"')]}
    body = {"type": "http.response.body", "body": b"hello"}

    weak = await _sent(start.copy(), body, request_headers=[(b"if-none-match", b'W/"v1"')])
    strong = await _sent(start.copy(), body, request_headers=[(b"if-none-match", b'"v1"')])

    assert (weak[0]["status"], strong[0]["status"]) == (304, 304)
