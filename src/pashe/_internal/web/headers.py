from __future__ import annotations

import enum
import hashlib
from http import HTTPStatus
from typing import TYPE_CHECKING, Final, Literal, NamedTuple, final, get_args

from pashe.errors import InvalidOptionsError
from pashe.hooks import CacheStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pashe.hooks import Outcome


@final
@enum.unique
class Header(enum.StrEnum):
    CACHE_CONTROL = "cache-control"
    CACHE_STATUS = "cache-status"
    CONTENT_LENGTH = "content-length"
    CONTENT_TYPE = "content-type"
    ETAG = "etag"
    IF_NONE_MATCH = "if-none-match"
    PRAGMA = "pragma"
    RATELIMIT_LIMIT = "ratelimit-limit"
    RATELIMIT_REMAINING = "ratelimit-remaining"
    RATELIMIT_RESET = "ratelimit-reset"
    RETRY_AFTER = "retry-after"


@final
@enum.unique
class CacheControl(enum.StrEnum):
    # The directives of Cache-Control pashe writes (RFC 9111).
    NO_CACHE = "no-cache"
    MAX_AGE = "max-age"


_ETAG_BYTES: Final = 16
_WEAK: Final = "W/"  # a weak ETag, which If-None-Match compares as a strong one
_ANY: Final = "*"  # If-None-Match of any ETag
_FRESH_ENOUGH: Final = 1  # max-age counts whole seconds: a result fresh for less is revalidated
_CACHE_NAME: Final = "pashe"  # how Cache-Status (RFC 9211) names this cache
_HIT: Final = "hit"
_MISS: Final = "fwd=miss"
_BY_REQUEST: Final = "fwd=request"  # the request asked past the stored results, with no-cache
_BODY_HEADERS: Final = frozenset((Header.CONTENT_LENGTH, Header.CONTENT_TYPE))  # a 304 has no body they describe
type Directive = Literal["private", "public"]
"""Who may keep a response: "private", the client only, or "public", shared caches too."""
_DIRECTIVES: Final = frozenset(get_args(Directive.__value__))


type Headers = list[tuple[str, str]]


@final
class Response(NamedTuple):
    # a response with the headers of caching added, or turned into a 304
    status: int
    headers: Headers
    body: bytes


def add_cache_headers(
    status: int,
    headers: Sequence[tuple[str, str]],
    body: bytes,
    *,
    if_none_match: str | None,
    calls: Sequence[Outcome],
    cache_control: Directive,
    no_cache: bool,
) -> Response:
    """``status`` is one cacheable took: the transports check it before they hold the body back."""
    present = {name.lower(): value for name, value in headers}
    etag = present.get(Header.ETAG) or _etag(body)  # hashed only when the endpoint set none
    # .value: a WSGI server, such as wsgiref, takes a name of type str only, not a StrEnum
    full = [*headers, *([] if Header.ETAG in present else [(Header.ETAG.value, etag)])]

    if calls:
        full += _freshness(calls, cache_control, has_cache_control=Header.CACHE_CONTROL in present, no_cache=no_cache)

    if has_matching_etag(if_none_match, etag):
        return Response(
            HTTPStatus.NOT_MODIFIED, [(name, value) for name, value in full if name.lower() not in _BODY_HEADERS], b""
        )
    return Response(status, full, body)


def honors_no_cache[R](
    allow: Callable[[R], bool] | None,
    request: R,
    *,
    cache_control: str | None,
    pragma: str | None,
) -> bool:
    """Whether a request asks past every stored result, and allow lets it.

    Cache-Control: no-cache or the Pragma of HTTP/1.0 asks; max-age=0, which a browser
    sends on a plain reload, does not.
    """
    if allow is None:
        return False
    asked = _directives(cache_control) | _directives(pragma)
    return CacheControl.NO_CACHE in asked and allow(request)


def is_cacheable(status: int) -> bool:
    """Only a 200 gets an ETag and the freshness of its results: another status says nothing they describe."""
    return status == HTTPStatus.OK


def parse_cache_control(cache_control: object) -> Directive:
    if cache_control not in _DIRECTIVES:
        msg = f'cache_control is {cache_control!r}: "private", the client only, or "public"'
        raise InvalidOptionsError(msg)
    return cache_control  # type: ignore[return-value]  # one of _DIRECTIVES: just checked


def has_matching_etag(if_none_match: str | None, tag: str) -> bool:
    if if_none_match is None:
        return False
    # the weak comparison of RFC 9110: a W/ on either side does not count
    named = {name.strip().removeprefix(_WEAK) for name in if_none_match.split(",")}
    return _ANY in named or tag.removeprefix(_WEAK) in named


def _freshness(
    calls: Sequence[Outcome],
    cache_control: Directive,
    *,
    has_cache_control: bool,
    no_cache: bool,
) -> Headers:
    """A response is as fresh as its shortest-lived result; one that was not stored is not fresh."""
    shortest = min(call.fresh_seconds or 0 for call in calls)
    added: Headers = []
    if not has_cache_control:  # the endpoint decided itself
        fresh = f"{CacheControl.MAX_AGE}={int(shortest)}" if shortest >= _FRESH_ENOUGH else CacheControl.NO_CACHE
        added.append((Header.CACHE_CONTROL.value, f"{cache_control}, {fresh}"))

    hit = all(call.status is not CacheStatus.MISS for call in calls)
    forwarded = _HIT if hit else _MISS
    status = [_CACHE_NAME, _BY_REQUEST if no_cache else forwarded]
    if all(call.fresh_seconds is not None for call in calls):
        status.append(f"ttl={int(shortest)}")
    added.append((Header.CACHE_STATUS.value, "; ".join(status)))

    return added


def _etag(body: bytes) -> str:
    digest = hashlib.blake2b(body, digest_size=_ETAG_BYTES).hexdigest()
    return f'"{digest}"'


def _directives(value: str | None) -> set[str]:
    """The names of the directives of a header such as Cache-Control, in lower case."""
    return {part.partition("=")[0].strip().lower() for part in (value or "").split(",")}
