"""ASGI: HTTP caching of GET responses made of cached calls, and rate limits of requests, for any ASGI application.

FastAPI, Starlette, Litestar, Quart and Django under ASGI all take them::

    app.add_middleware(CacheHeadersMiddleware, hook=headers)  # FastAPI, Starlette
    Litestar(route_handlers=[...], middleware=[DefineMiddleware(CacheHeadersMiddleware, hook=headers)])
    application = CacheHeadersMiddleware(application, hook=headers)  # any ASGI application

where headers is the CacheHeadersHook of pashe.hooks the caches of the application were given.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Callable
from http import HTTPMethod, HTTPStatus
from typing import TYPE_CHECKING, Any, Final, final

from pashe import AsyncCache
from pashe._internal.cache.call import no_cache
from pashe._internal.checks import FUNCTION, expect_type
from pashe._internal.limits import LIMIT, parse_cost, rate_limit_headers
from pashe._internal.web.headers import (
    Directive,
    Header,
    add_cache_headers,
    allows_no_cache,
    is_cacheable,
    parse_cache_control,
)
from pashe.errors import RateLimitedError
from pashe.hooks import CacheHeadersHook

if TYPE_CHECKING:
    from collections.abc import Awaitable, Iterable, MutableMapping, Sequence

    from pashe._internal.web.headers import Headers
    from pashe.hooks import Outcome
    from pashe.ratelimit import Limit

__all__ = ["CacheHeadersMiddleware", "RateLimitMiddleware"]

# The types of the ASGI specification, by the names starlette.types gives them.
type Scope = MutableMapping[str, Any]  # what the server tells of a connection: its type, method, path and headers
type Message = MutableMapping[str, Any]  # an event of the connection, such as http.response.start
type Receive = Callable[[], Awaitable[Message]]
type Send = Callable[[Message], Awaitable[None]]
type ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_START: Final = "http.response.start"
_BODY: Final = "http.response.body"
_LATIN1: Final = "latin-1"  # the charset of HTTP header bytes in ASGI


@final
class CacheHeadersMiddleware:
    """Tells clients how long a GET response stays valid, and answers 304 when it did not change.

    Every successful GET response gets an ETag of its body, and one that If-None-Match names is
    answered 304 without the body: the endpoint still runs, the body does not travel. A response
    the endpoint made with cached calls also gets Cache-Control, fresh as long as its
    shortest-lived result, unless the endpoint set one, and Cache-Status (RFC 9211). A streamed
    response passes as it is.

    Examples:
        >>> from fastapi import FastAPI
        >>> from pashe.asgi import CacheHeadersMiddleware
        >>> from pashe.hooks import CacheHeadersHook
        >>> app = FastAPI()
        >>> app.add_middleware(CacheHeadersMiddleware, hook=CacheHeadersHook(), cache_control="public")
    """

    __slots__ = ("_allow_no_cache", "_app", "_cache_control", "_hook")

    def __init__(
        self,
        app: ASGIApp,  # by name too: frameworks make a middleware as cls(app=app, ...)
        *,
        hook: CacheHeadersHook,
        cache_control: Directive = "private",
        allow_no_cache: Callable[[Scope], bool] | None = None,
    ) -> None:
        """Wrap app.

        Args:
            app: the ASGI application.
            hook: the hook of the caches the application calls, which records their calls.
            cache_control: who may keep a response: "private", the client only, as cached data may
                belong to one user; "public" lets shared caches keep it too.
            allow_no_cache: given the scope of a request with ``Cache-Control: no-cache``, whether
                it may load past the stored results, which then store what it loaded, as in
                pashe.no_cache; none may by default. Any client can send the header, and every
                such request loads from the source: let only those you trust, such as staff.

        Raises:
            TypeError: app is not an application, or hook not a CacheHeadersHook.
            InvalidOptionsError: cache_control is neither "private" nor "public".
        """
        expect_type("app", app, FUNCTION)
        expect_type("hook", hook, CacheHeadersHook)
        expect_type("allow_no_cache", allow_no_cache, FUNCTION | None)

        self._app = app
        self._cache_control: Directive = parse_cache_control(cache_control)
        self._hook = hook
        self._allow_no_cache = allow_no_cache

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Run the request, and add the headers of caching to a GET response.

        Args:
            scope: the ASGI scope of the connection.
            receive: receives the messages of the request.
            send: sends the messages of the response.
        """
        if scope["type"] != "http" or scope["method"] != HTTPMethod.GET:
            await self._app(scope, receive, send)
            return
        headers = _joined(scope["headers"])
        reload = allows_no_cache(
            self._allow_no_cache,
            scope,
            cache_control=headers.get(Header.CACHE_CONTROL),
            pragma=headers.get(Header.PRAGMA),
        )
        with self._hook.recording() as calls, no_cache() if reload else contextlib.nullcontext():
            held = _HeldResponse(
                send,
                if_none_match=headers.get(Header.IF_NONE_MATCH),
                calls=calls,
                cache_control=self._cache_control,
                no_cache=reload,
            )
            await self._app(scope, receive, held.send)


@final
class RateLimitMiddleware:
    """Counts every HTTP request under the key key gives it, and answers 429 to one over limit.

    A request let through gets the RateLimit-Limit, RateLimit-Remaining and RateLimit-Reset
    headers; one over the limit gets 429 Too Many Requests with Retry-After, and the application
    never sees it. Give it to the whole application, or to one route of a framework that takes
    middleware per route, as Starlette and Litestar do. A route of FastAPI, or a limit by a user
    other dependencies found, takes rate_limit of pashe.contrib.fastapi instead.

    Examples:
        >>> from starlette.applications import Starlette
        >>> from starlette.middleware import Middleware
        >>> from pashe import AsyncCache
        >>> from pashe.asgi import RateLimitMiddleware
        >>> from pashe.backends import AsyncMemoryBackend
        >>> from pashe.ratelimit import per_minute
        >>> cache = AsyncCache(AsyncMemoryBackend())
        >>> def client(scope) -> str:
        ...     return dict(scope["headers"])[b"x-forwarded-for"].decode().split(",")[0]
        >>> app = Starlette(
        ...     middleware=[Middleware(RateLimitMiddleware, cache=cache, limit=per_minute(100), key=client)]
        ... )
    """

    __slots__ = ("_app", "_cache", "_cost", "_fail_open", "_key", "_limit")

    def __init__(
        self,
        app: ASGIApp,  # by name too: frameworks make a middleware as cls(app=app, ...)
        *,
        cache: AsyncCache,
        limit: Limit,
        key: Callable[[Scope], str],
        cost: int = 1,
        fail_open: bool = True,
    ) -> None:
        """Wrap app.

        Args:
            app: the ASGI application, or the route.
            cache: the cache whose backend keeps the counters.
            limit: the limit, such as ``per_minute(100)``.
            key: what a request counts under, from its scope, such as the address of its client;
                required, as behind a proxy the address of the connection is the address of the proxy.
            cost: how many calls a request counts as.
            fail_open: let a request through when the backend fails; off, it raises BackendError.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: cost is not from 1 to the calls of the limit.
        """
        expect_type("app", app, FUNCTION)
        expect_type("cache", cache, AsyncCache)
        expect_type("limit", limit, LIMIT)
        expect_type("key", key, FUNCTION)
        expect_type("fail_open", fail_open, bool)

        self._app = app
        self._cache = cache
        self._limit = limit
        self._key = key
        self._cost = parse_cost(limit, cost)
        self._fail_open = fail_open

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Count the request, and run it or refuse it.

        Args:
            scope: the ASGI scope of the connection.
            receive: receives the messages of the request.
            send: sends the messages of the response.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        try:
            state = await self._cache.rate_limit(
                self._key(scope), self._limit, cost=self._cost, fail_open=self._fail_open
            )
        except RateLimitedError as error:
            await _refuse(send, error.retry_after)
            return
        if state is None:  # the backend failed and the request goes through uncounted
            await self._app(scope, receive, send)
            return
        told = _RateLimitHeadersSender(send, _encoded(rate_limit_headers(state).items()))
        await self._app(scope, receive, told.send)


@final
class _RateLimitHeadersSender:
    # sends the response with the RateLimit headers of the request added to its start
    __slots__ = ("_headers", "_send")

    def __init__(self, send: Send, headers: list[tuple[bytes, bytes]]) -> None:
        self._send = send
        self._headers = headers

    async def send(self, message: Message) -> None:
        if message["type"] == _START:
            message["headers"] = [*message.get("headers", []), *self._headers]
        await self._send(message)


@final
class _HeldResponse:
    __slots__ = ("_cache_control", "_calls", "_if_none_match", "_no_cache", "_send", "_start")

    def __init__(
        self,
        send: Send,
        *,
        if_none_match: str | None,
        calls: Sequence[Outcome],
        cache_control: Directive,
        no_cache: bool,
    ) -> None:
        self._send = send
        self._if_none_match = if_none_match
        self._calls = calls  # filled while the endpoint runs, read when the body is whole
        self._cache_control: Directive = cache_control
        self._no_cache = no_cache

        self._start: Message | None = None

    async def send(self, message: Message) -> None:
        kind = message["type"]
        if kind == _START and is_cacheable(message["status"]):
            self._start = message
        elif kind == _BODY and self._start is not None and not message.get("more_body", False):
            await self._finish(self._start, message.get("body", b""))
        else:  # a streamed body, an error or an extension such as pathsend: no ETag for it
            if self._start is not None:  # the start held back goes first
                await self._send(self._start)
                self._start = None
            await self._send(message)

    async def _finish(self, start: Message, whole: bytes) -> None:
        self._start = None
        status, headers, body = add_cache_headers(
            start["status"],
            _decoded(start.get("headers", [])),
            whole,
            if_none_match=self._if_none_match,
            calls=self._calls,
            cache_control=self._cache_control,
            no_cache=self._no_cache,
        )

        start["status"] = status
        start["headers"] = _encoded(headers)
        await self._send(start)
        await self._send({"type": _BODY, "body": body})


def _joined(raw: Iterable[tuple[bytes, bytes]]) -> dict[str, str]:
    # one value a name, repeated lines joined with commas, as a WSGI server joins them
    joined: dict[str, str] = {}
    for name, value in _decoded(raw):
        joined[name] = f"{joined[name]},{value}" if name in joined else value
    return joined


def _decoded(raw: Iterable[tuple[bytes, bytes]]) -> Headers:
    return [(name.decode(_LATIN1), value.decode(_LATIN1)) for name, value in raw]


def _encoded(headers: Iterable[tuple[str, str]]) -> list[tuple[bytes, bytes]]:
    return [(name.encode(_LATIN1), value.encode(_LATIN1)) for name, value in headers]


async def _refuse(send: Send, retry_after: float) -> None:
    body = b"Too Many Requests"
    headers = [
        (Header.RETRY_AFTER, str(math.ceil(retry_after))),
        (Header.CONTENT_TYPE, "text/plain; charset=utf-8"),
        (Header.CONTENT_LENGTH, str(len(body))),
    ]
    await send({"type": _START, "status": HTTPStatus.TOO_MANY_REQUESTS, "headers": _encoded(headers)})
    await send({"type": _BODY, "body": body})
