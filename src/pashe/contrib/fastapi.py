"""FastAPI: rate limits of routes; the fastapi extra.

The headers of caching come from pashe.asgi, with the CacheHeadersHook of pashe.hooks::

    headers = CacheHeadersHook()
    cache = AsyncCache(backend, hooks=[headers])
    app = FastAPI()
    app.add_middleware(CacheHeadersMiddleware, hook=headers)


    @app.get("/search", dependencies=[Depends(rate_limit(cache, per_minute(100), key=client_key))])
    async def search() -> list[Result]: ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from pashe import AsyncCache
from pashe._internal.checks import FUNCTION, expect_type
from pashe._internal.limits import LIMIT, parse_cost, rate_limit_headers
from pashe.errors import MissingExtraError
from pashe.ratelimit import RateLimitState  # noqa: TC001 - FastAPI reads the annotations of a dependency at runtime

try:
    from fastapi import Request, Response  # noqa: TC002 - FastAPI reads the annotations of a dependency at runtime
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "fastapi", name=error.name) from error

if TYPE_CHECKING:
    from collections.abc import Callable

    from pashe.ratelimit import Limit

__all__ = ["rate_limit"]


@final
class rate_limit:  # noqa: N801 - a dependency is named as what it does, as Depends(rate_limit(...)) reads
    """A dependency that counts a request under the key key gives it, and tells what is left in RateLimit headers.

    Over the limit it raises RateLimitedError: answer it with an exception handler of the app.
    It runs with the route, so its key may read what other dependencies made, such as the user.
    For every request of the application, take RateLimitMiddleware of pashe.asgi.

    Examples:
        >>> from fastapi import Depends, FastAPI, Request
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> from pashe.contrib.fastapi import rate_limit
        >>> from pashe.ratelimit import per_minute
        >>> cache = AsyncCache(AsyncMemoryBackend())
        >>> app = FastAPI()
        >>> def client_key(request: Request) -> str:
        ...     return request.headers["x-forwarded-for"].split(",")[0]
        >>> @app.get("/search", dependencies=[Depends(rate_limit(cache, per_minute(100), key=client_key))])
        ... async def search() -> list[str]:
        ...     return []
    """

    __slots__ = ("_cache", "_cost", "_fail_open", "_key", "_limit")

    def __init__(
        self,
        cache: AsyncCache,
        limit: Limit,
        /,
        *,
        key: Callable[[Request], str],
        cost: int = 1,
        fail_open: bool = True,
    ) -> None:
        """Count requests against limit in cache.

        Args:
            cache: the cache whose backend keeps the counters.
            limit: the limit, such as ``per_minute(100)``.
            key: what to count a request under, such as the address of its client; required, as
                behind a proxy the address of the connection is the address of the proxy.
            cost: how many calls a request counts as.
            fail_open: let a request through when the backend fails; off, raise BackendError.

        Raises:
            TypeError: an argument is not of the type its annotation names.
            InvalidOptionsError: cost is not from 1 to the calls of the limit.
        """
        expect_type("cache", cache, AsyncCache)
        expect_type("limit", limit, LIMIT)
        expect_type("key", key, FUNCTION)
        cost = parse_cost(limit, cost)
        expect_type("fail_open", fail_open, bool)

        self._cache = cache
        self._limit = limit
        self._key = key
        self._cost = cost
        self._fail_open = fail_open

    async def __call__(self, request: Request, response: Response) -> RateLimitState | None:
        """Count the request; FastAPI calls it for every request of the route.

        Args:
            request: the request.
            response: the response, which gets the RateLimit headers.

        Returns:
            What is left of the limit; None if the backend failed and the request went through.

        Raises:
            RateLimitedError: the request is over the limit.
        """
        state = await self._cache.rate_limit(
            self._key(request), self._limit, cost=self._cost, fail_open=self._fail_open
        )
        if state is not None:
            response.headers.update(rate_limit_headers(state))
        return state
