"""The meta commands of memcached both sides send, and how an answer reads: no I/O here.

Every key goes as base64 with the b flag, so any text is a key; memcached takes 250 bytes of the
encoded key at most, so a longer key goes as a digest of it.
"""

from __future__ import annotations

import base64
import hashlib
import math
from dataclasses import dataclass
from typing import Final

from pashe.errors import BackendError

_MAX_KEY_BYTES: Final = 186  # base64 of 187 bytes is 252, past the 250 memcached takes
# A digest starts with a byte no key of text starts with, so it can't be taken for a short key
_DIGEST_MARK: Final = b"\x00"
_DIGEST_BYTES: Final = 32
_RELATIVE_TTL_LIMIT: Final = 2_592_000  # 30 days: memcached reads a longer TTL as a Unix time
_NO_EXPIRY: Final = b"-1"  # what the t flag returns for an item with no TTL

NO_OP: Final = b"mn\r\n"


@dataclass(frozen=True, slots=True, kw_only=True)
class Answer:
    """One answer of memcached: its code, such as HD or EN, its flags, and the value of a VA."""

    code: bytes
    flags: dict[bytes, bytes]
    value: bytes | None = None

    @property
    def cas(self) -> int:
        """The CAS token, which the c flag asks for."""
        return int(self.flags[b"c"])

    @property
    def seconds_left(self) -> float:
        """What the t flag returns: the seconds left, math.inf for an item with no TTL."""
        left = self.flags[b"t"]
        return math.inf if left == _NO_EXPIRY else float(left)


def get(key: str, flags: bytes) -> bytes:
    """An mg of key with flags, such as b"v c" for the value and its CAS token."""
    return b"mg %b b %b\r\n" % (_encoded(key), flags)


def store(
    key: str,
    value: bytes,
    flags: bytes,
) -> bytes:
    """An ms of value under key with flags, such as b"T60 ME" to add it for a minute."""
    return b"ms %b %d b %b\r\n%b\r\n" % (_encoded(key), len(value), flags, value)


def delete(key: str, flags: bytes = b"") -> bytes:
    """An md of key with flags, such as b"C42" to delete it only if its CAS token is 42."""
    return b"md %b b %b\r\n" % (_encoded(key), flags)


def ttl_flag(ttl: float | None, now: float) -> bytes:
    """The T flag for ttl seconds from now, rounded up to whole ones; None never expires.

    Past 30 days memcached reads the number as a Unix time, so such a TTL goes as one.
    """
    if ttl is None:
        return b"T0"
    seconds = max(1, math.ceil(ttl))  # T0 would never expire
    if seconds > _RELATIVE_TTL_LIMIT:
        return b"T%d" % math.ceil(now + ttl)
    return b"T%d" % seconds


def read_header(line: bytes) -> tuple[Answer, int | None]:
    """The answer a line starts, and the size of the value that follows it, for a VA.

    A SERVER_ERROR, such as for a value too large, is BackendError; a command memcached refused as
    malformed is a bug of pashe, a RuntimeError.
    """
    if not line.endswith(b"\r\n"):
        msg = "memcached: the connection closed in the middle of an answer"
        raise BackendError(msg)

    code, *tokens = line[:-2].split(b" ")
    text = line[:-2].decode(errors="replace")
    if code == b"SERVER_ERROR":
        msg = f"memcached: {text}"
        raise BackendError(msg)
    if code in {b"CLIENT_ERROR", b"ERROR"}:
        msg = f"memcached refused a command of pashe: {text}"
        raise RuntimeError(msg)

    if code == b"VA":
        size, *tokens = tokens
        return Answer(code=code, flags=_flags(tokens)), int(size)
    return Answer(code=code, flags=_flags(tokens)), None


def _flags(tokens: list[bytes]) -> dict[bytes, bytes]:
    return {token[:1]: token[1:] for token in tokens}


def _encoded(key: str) -> bytes:
    raw = key.encode()
    if len(raw) > _MAX_KEY_BYTES:
        raw = _DIGEST_MARK + hashlib.blake2b(raw, digest_size=_DIGEST_BYTES).digest()
    return base64.b64encode(raw)
