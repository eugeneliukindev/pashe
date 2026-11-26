from __future__ import annotations

import math
import random
import time
from typing import TYPE_CHECKING, Final, final

from redis.exceptions import ResponseError

from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

POLL: Final = 1.0  # seconds a pub/sub bus waits for a message before it checks again
_FIRST_RETRY: Final = 1.0  # seconds a bus waits before it listens again after Redis failed
_LONGEST_RETRY: Final = 30.0
_RETRY_JITTER: Final = 0.5  # a wait is cut by up to this share, so processes do not reconnect together
INVALIDATE_CHANNEL: Final = "__redis__:invalidate"  # the channel tracking sends its messages to over RESP2
_RESP3_ONLY: Final = "maint_notifications"  # settings of a pool that a RESP2 connection refuses


@final
class ReconnectBackoff:
    # How long a bus waits before it listens again: it doubles while Redis keeps failing, so the
    # processes of a service do not all hammer a Redis that is down, and starts over after a calm.
    __slots__ = ("_clock", "_delay", "_failed_at")

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock

        self._delay: float = 0
        self._failed_at = -math.inf

    def next_delay(self) -> float:
        now = self._clock()
        calm = now - self._failed_at > 2 * _LONGEST_RETRY  # listened long enough since the last failure
        self._delay = _FIRST_RETRY if calm else min(self._delay * 2, _LONGEST_RETRY)
        self._failed_at = now
        return self._delay * random.uniform(1 - _RETRY_JITTER, 1)  # noqa: S311 - jitter, not a secret


def listen_failure(error: Exception) -> Failure:
    """An error of a listener other than a lost connection, such as of the near cache it calls: told, not dropped."""
    return Failure(Operation.LISTEN, "", error)


def listening_connection[C](connection_class: type[C], settings: Mapping[str, object]) -> C:
    kept = {name: value for name, value in settings.items() if not name.startswith(_RESP3_ONLY)}
    return connection_class(**kept | {"protocol": 2, "socket_timeout": None})


def tracking_command(client_id: object, prefix: str) -> list[str | int]:
    """CLIENT TRACKING that redirects to the connection whose CLIENT ID answered client_id."""
    if not isinstance(client_id, int):
        msg = f"CLIENT ID answered {client_id!r}, not the id of a connection"
        raise ResponseError(msg)  # a RedisError: the listener reconnects
    prefixes = ["PREFIX", prefix] if prefix else []
    return ["CLIENT", "TRACKING", "ON", "REDIRECT", client_id, "BCAST", *prefixes]
