from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from pashe._internal.checks import parse_int
from pashe._internal.web.headers import Header
from pashe.ratelimit import FixedWindow, SlidingWindow

if TYPE_CHECKING:
    from pashe.ratelimit import Limit, RateLimitState

LIMIT: Final = SlidingWindow | FixedWindow  # what isinstance checks a Limit as


def parse_cost(limit: Limit, cost: object) -> int:
    """How many calls of limit a call counts as: more than the limit allows would refuse it every time."""
    return parse_int(
        "cost",
        cost,
        low=1,
        high=limit.calls,
        meaning=f"a call must cost from 1 to the {limit.calls} calls of its limit",
    )


def rate_limit_headers(state: RateLimitState) -> dict[str, str]:
    return {
        Header.RATELIMIT_LIMIT.value: str(state.limit),  # .value: str, as a WSGI server takes it
        Header.RATELIMIT_REMAINING.value: str(state.remaining),
        Header.RATELIMIT_RESET.value: str(math.ceil(state.reset_after)),
    }
