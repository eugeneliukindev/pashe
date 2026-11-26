# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# redis-py is typed in part: what its untyped methods return is unknown to pyright, as to mypy.
from __future__ import annotations

import contextlib
import inspect
import math
from typing import TYPE_CHECKING, Final

from redis.connection import AbstractConnection
from redis.exceptions import RedisError, ResponseError

from pashe.errors import BackendError, InvalidOptionsError, WrongTypeError

if TYPE_CHECKING:
    from collections.abc import Generator

    from redis import Redis
    from redis.asyncio import Redis as AsyncRedis
    from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster
    from redis.cluster import RedisCluster

_MILLISECONDS: Final = 1000
_NO_KEY: Final = -2  # what PTTL answers for a missing key
_NO_EXPIRY: Final = -1  # what PTTL answers for a key without a TTL
# what a connection of a client not given socket_timeout takes, as from_url: 5 seconds from redis-py 8, none before
_DEFAULT_TIMEOUT: Final = inspect.signature(AbstractConnection.__init__).parameters["socket_timeout"].default

# Compare-and-delete and compare-and-expire: only the owner of a lock releases or extends it.
DELETE_IF_EQUALS: Final = """
if redis.call("GET", KEYS[1]) == ARGV[1] then return redis.call("DEL", KEYS[1]) end
return 0
"""
EXPIRE_IF_EQUALS: Final = """
if redis.call("GET", KEYS[1]) == ARGV[1] then return redis.call("PEXPIRE", KEYS[1], ARGV[2]) end
return 0
"""

# Count in a key made with a TTL when it is missing: one key, so on a cluster one node runs it whole.
INCR_WITH_TTL: Final = """
redis.call("SET", KEYS[1], "0", "PX", ARGV[2], "NX")
return redis.call("INCRBY", KEYS[1], ARGV[1])
"""


@contextlib.contextmanager
def translated_errors() -> Generator[None]:
    """The errors of redis-py raised as those of pashe; an async call awaits in it as a sync one does."""
    try:
        yield
    except RedisError as error:
        raise translate_error(error) from error


def translate_error(error: RedisError) -> OverflowError | WrongTypeError | BackendError:
    msg = f"redis: {error}"
    if isinstance(error, ResponseError) and "overflow" in msg:
        return OverflowError(msg)
    if isinstance(error, ResponseError) and ("not an integer" in msg or "WRONGTYPE" in msg):
        return WrongTypeError(msg)  # an error a caller tells apart by its type
    return BackendError(msg)


def check_client(client: Redis | AsyncRedis | RedisCluster | AsyncRedisCluster) -> None:
    settings = client.get_connection_kwargs()
    if settings.get("decode_responses"):
        msg = "redis: a backend needs a client without decode_responses: it stores bytes"
        raise InvalidOptionsError(msg)
    # a Redis that hangs would hang every call, past the breaker
    if settings.get("socket_timeout", _DEFAULT_TIMEOUT) is None:
        msg = "redis: a backend needs a client with socket_timeout, such as Redis.from_url(url, socket_timeout=1)"
        raise InvalidOptionsError(msg)


def px(ttl: float | None) -> int | None:
    return None if ttl is None else milliseconds(ttl)


def milliseconds(ttl: float) -> int:
    return max(1, math.ceil(ttl * _MILLISECONDS))


def seconds_left(pttl: int) -> float | None:
    if pttl == _NO_KEY:
        return None
    if pttl == _NO_EXPIRY:
        return math.inf
    return pttl / _MILLISECONDS
