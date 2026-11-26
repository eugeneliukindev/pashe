"""Properties of the pure parts of pashe: what holds for every input, not only for the examples of the other tests."""

from __future__ import annotations

import contextlib
import itertools
import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from pashe import Cache
from pashe._internal.cache.entry import Entry, pack, unpack
from pashe._internal.cache.keys import canonical
from pashe._internal.redis.listening import ReconnectBackoff
from pashe._internal.web.headers import has_matching_etag
from pashe.backends import MemoryBackend
from pashe.errors import CodecError, RateLimitedError
from pashe.ratelimit import RateLimitState, SlidingWindow
from tests.harness.helpers import Clock

_INT64 = st.integers(-(2**63), 2**63 - 1)
_SECONDS = st.floats(0.001, 1e6, allow_nan=False, allow_infinity=False)
_NOW = st.floats(0, 1e10, allow_nan=False, allow_infinity=False)
_ENTRIES = st.builds(
    Entry,
    stale_at=st.floats(allow_nan=False),
    negative=st.booleans(),
    compressed=st.booleans(),
    type_fingerprint=st.integers(0, 2**64 - 1),
    tag_generations=st.lists(_INT64, max_size=4).map(tuple),
    payload=st.binary(),
)


@given(_ENTRIES)
def test_an_entry_reads_back_as_it_was_stored(entry: Entry) -> None:
    assert unpack(pack(entry)) == entry


@given(st.binary())
def test_bytes_from_the_backend_are_an_entry_or_a_codec_error(raw: bytes) -> None:
    with contextlib.suppress(CodecError):  # what a cache reads as a miss
        unpack(raw)


@given(st.integers(1, 20), _SECONDS, _NOW, st.integers(1, 40))
def test_what_is_left_of_a_sliding_limit_stays_within_it(calls: int, per: float, now: float, made: int) -> None:
    clock = Clock()
    clock.now = now
    cache = Cache(MemoryBackend(), clock=clock)
    limit = SlidingWindow(calls=calls, per=per)

    states: list[RateLimitState | None] = []
    for _ in range(made):
        with contextlib.suppress(RateLimitedError):
            states.append(cache.rate_limit("api", limit))

    assert states  # the first call always passes
    assert all(state is not None and 0 <= state.remaining <= calls for state in states)
    assert all(state is not None and 0 < state.reset_after <= per for state in states)


@given(st.integers(1, 20), _SECONDS, _NOW, st.integers(0, 40), st.lists(st.integers(1, 20), min_size=1, max_size=40))
def test_a_refused_call_waits_a_finite_time_that_is_not_negative(
    calls: int, per: float, now: float, before: int, costs: list[int]
) -> None:
    assume(all(cost <= calls for cost in costs))
    clock = Clock()
    clock.now = now
    cache = Cache(MemoryBackend(), clock=clock)
    limit = SlidingWindow(calls=calls, per=per)
    for _ in range(before):  # the last window, which the sliding one still overlaps
        with contextlib.suppress(RateLimitedError):
            cache.rate_limit("api", limit)
    clock.now += per

    waits = []
    for cost in costs:  # calls of different costs: one may not fit in the window the others left
        try:
            cache.rate_limit("api", limit, cost=cost)
        except RateLimitedError as refused:
            waits.append(refused.retry_after)

    assert all(wait >= 0 for wait in waits)
    assert all(math.isfinite(wait) for wait in waits)


@given(st.integers(1, 20), _SECONDS, _NOW, st.lists(st.integers(1, 20), min_size=1, max_size=40))
def test_a_call_made_after_its_retry_after_passes(calls: int, per: float, now: float, costs: list[int]) -> None:
    assume(all(cost <= calls for cost in costs))
    clock = Clock()
    clock.now = now
    cache = Cache(MemoryBackend(clock=clock), clock=clock)
    limit = SlidingWindow(calls=calls, per=per)

    waits = []
    for cost in costs:
        try:
            cache.rate_limit("api", limit, cost=cost)
        except RateLimitedError as refused:
            waits.append(refused.retry_after)
            clock.now += refused.retry_after
            cache.rate_limit("api", limit, cost=cost)  # raises if the wait was not enough

    assert all(wait > 0 for wait in waits)


@given(st.text(alphabet=st.characters(blacklist_characters=",", blacklist_categories=["Zs", "Cc"]), min_size=1))
def test_if_none_match_names_the_tag_it_was_given(digest: str) -> None:
    tag = f'"{digest}"'
    assert has_matching_etag(tag, tag)
    assert has_matching_etag(f"W/{tag}", tag)  # compared weakly, as RFC 9110 says
    assert has_matching_etag(f'"other", {tag}', tag)


@given(st.dictionaries(st.text(), st.integers() | st.text() | st.booleans() | st.none()))
def test_equal_values_give_one_canonical_form(values: dict[str, object]) -> None:
    reversed_order = dict(reversed(values.items()))
    assert canonical(values) == canonical(reversed_order)
    assert canonical(set(values)) == canonical(set(reversed_order))


@pytest.mark.parametrize("raw", [b"", b"\x02", b"\x01" + bytes(19)])
def test_a_cut_or_older_entry_is_a_codec_error(raw: bytes) -> None:
    with pytest.raises(CodecError):
        unpack(raw)


def test_a_bus_waits_longer_while_redis_keeps_failing_and_starts_over_after_a_calm() -> None:
    clock = Clock()
    backoff = ReconnectBackoff(clock)

    waits = []
    for _ in range(8):
        waits.append(backoff.next_delay())
        clock.now += 1
    clock.now += 600  # Redis answered for ten minutes
    after_calm = backoff.next_delay()

    assert all(earlier <= later * 2 for earlier, later in itertools.pairwise(waits))
    assert 0.5 <= waits[0] <= 1  # the first wait, jitter applied
    assert max(waits) <= 30
    assert waits[-1] >= 15  # it grew to the longest, jitter applied
    assert after_calm <= 1
