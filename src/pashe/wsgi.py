"""WSGI: HTTP caching of GET responses made of cached calls, for any WSGI application.

Django and Flask under WSGI take it::

    application = CacheHeadersMiddleware(application, hook=headers)

where headers is the CacheHeadersHook of pashe.hooks the caches of the application were given.
"""

from __future__ import annotations

import contextlib
import contextvars
import itertools
from http import HTTPMethod, HTTPStatus
from typing import TYPE_CHECKING, Final, final

from pashe._internal.cache.call import in_no_cache, no_cache
from pashe._internal.checks import FUNCTION, expect_type
from pashe._internal.web.headers import (
    Directive,
    Header,
    Headers,
    add_cache_headers,
    honors_no_cache,
    is_cacheable,
    parse_cache_control,
)
from pashe.hooks import CacheHeadersHook

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Iterator
    from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

    from _typeshed import OptExcInfo


__all__ = ["CacheHeadersMiddleware"]

# WSGI hands a request header as HTTP_ and its name in upper case, dashes turned into underscores.
_IF_NONE_MATCH: Final = "HTTP_IF_NONE_MATCH"
_CACHE_CONTROL: Final = "HTTP_CACHE_CONTROL"
_PRAGMA: Final = "HTTP_PRAGMA"


@final
class CacheHeadersMiddleware:
    """Tells clients how long a GET response stays valid, and answers 304 when it did not change.

    It does what pashe.asgi.CacheHeadersMiddleware does. A response without
    Content-Length may be streamed, so it passes as it is.

    Examples:
        >>> from pashe.wsgi import CacheHeadersMiddleware
        >>> def application(environ, start_response):
        ...     start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "2")])
        ...     return [b"ok"]
        >>> from pashe.hooks import CacheHeadersHook
        >>> application = CacheHeadersMiddleware(application, hook=CacheHeadersHook())
    """

    __slots__ = ("_app", "_cache_control", "_honor_no_cache", "_hook")

    def __init__(
        self,
        app: WSGIApplication,
        /,
        *,
        hook: CacheHeadersHook,
        cache_control: Directive = "private",
        honor_no_cache: Callable[[WSGIEnvironment], bool] | None = None,
    ) -> None:
        """Wrap app.

        Args:
            app: the WSGI application.
            hook: the hook of the caches the application calls, which records their calls.
            cache_control: who may keep a response: "private", the client only, as cached data may
                belong to one user; "public" lets shared caches keep it too.
            honor_no_cache: given the environment of a request with ``Cache-Control: no-cache``,
                whether it may load past the stored results, which then store what it loaded, as
                in pashe.no_cache; none may by default. Any client can send the header, and every
                such request loads from the source: let only those you trust, such as staff.

        Raises:
            TypeError: app is not an application, or hook not a CacheHeadersHook.
            InvalidOptionsError: cache_control is neither "private" nor "public".
        """
        expect_type("app", app, FUNCTION)
        expect_type("hook", hook, CacheHeadersHook)
        expect_type("honor_no_cache", honor_no_cache, FUNCTION | None)

        self._app = app
        self._cache_control: Directive = parse_cache_control(cache_control)
        self._hook = hook
        self._honor_no_cache = honor_no_cache

    def __call__(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        """Run the request, and add the headers of caching to a GET response.

        Args:
            environ: the WSGI environment of the request.
            start_response: starts the response.

        Returns:
            The body of the response.
        """
        if environ["REQUEST_METHOD"] != HTTPMethod.GET:
            return self._app(environ, start_response)
        started = _Started()
        with self._hook.recording() as calls, no_cache() if self._reloads(environ) else contextlib.nullcontext():
            app_iter = self._app(environ, started.start_response)
            with _closed_if_it_fails(app_iter):
                chunks = iter(app_iter)
                head = [
                    *started.written,
                    *itertools.islice(chunks, 1),
                ]  # an application may start the response when iterated
                code = int(started.status.split(maxsplit=1)[0])

                # Only a whole body has an ETag: one without its length streams through as it is.
                if not is_cacheable(code) or all(name.lower() != Header.CONTENT_LENGTH for name, _ in started.headers):
                    start_response(started.status, started.headers, started.exc_info)
                    return _Rest(head, chunks, app_iter, context=contextvars.copy_context())
            try:
                body = b"".join([*head, *chunks])
            finally:
                _close(app_iter)

            code, headers, body = add_cache_headers(
                code,
                started.headers,
                body,
                if_none_match=environ.get(_IF_NONE_MATCH),
                calls=calls,
                cache_control=self._cache_control,
                no_cache=in_no_cache(),
            )
        start_response(f"{code} {HTTPStatus(code).phrase}", headers, started.exc_info)
        return [body]

    def _reloads(self, environ: WSGIEnvironment) -> bool:
        return honors_no_cache(
            self._honor_no_cache, environ, cache_control=environ.get(_CACHE_CONTROL), pragma=environ.get(_PRAGMA)
        )


@final
class _Started:  # what the application passed to start_response
    __slots__ = ("exc_info", "headers", "status", "written")

    def __init__(self) -> None:
        self.status = ""
        self.headers: Headers = []
        self.exc_info: OptExcInfo | None = None
        self.written: list[bytes] = []

    def start_response(
        self,
        status: str,
        headers: Headers,
        exc_info: OptExcInfo | None = None,
        /,
    ) -> Callable[[bytes], object]:
        self.status = status
        self.headers = headers
        self.exc_info = exc_info
        return self.written.append


@final
class _Rest:
    # the body that streams after the middleware returned, still in the context of the request, as no_cache
    __slots__ = ("_app_iter", "_chunks", "_context")

    def __init__(
        self,
        head: list[bytes],
        chunks: Iterator[bytes],
        app_iter: Iterable[bytes],
        *,
        context: contextvars.Context,
    ) -> None:
        self._chunks = itertools.chain(head, chunks)
        self._app_iter = app_iter
        self._context = context

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        return self._context.run(next, self._chunks)

    def close(self) -> None:
        _close(self._app_iter)


@contextlib.contextmanager
def _closed_if_it_fails(app_iter: Iterable[bytes]) -> Generator[None]:
    # closed whatever fails before the body is handed on, as PEP 3333 asks: Django finishes a request in close
    try:
        yield
    except BaseException:
        _close(app_iter)
        raise


def _close(app_iter: Iterable[bytes]) -> None:
    close = getattr(app_iter, "close", None)
    if close is not None:
        close()
