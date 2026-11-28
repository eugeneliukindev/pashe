from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, NamedTuple, Self, final

from pashe._internal.cache.call import Answer
from pashe._internal.checks import duration_seconds, parse_ttl, validate_type
from pashe.errors import InvalidOptionsError, NotFoundError, OverloadedError
from pashe.hooks import CacheStatus
from pashe.options import Negative, Stale, Stampede, Store

if TYPE_CHECKING:
    from collections.abc import Callable

    from pashe._internal.cache.entry import Stored
    from pashe.options import TTL, Duration

_TTL_MEANING: Final = "how long a result is fresh"


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    # How one cached function behaves, from its options checked once, here: its function cache asks
    # it and trusts it. Only decisions: encoding is EntryFormat's, telling the hooks the caller's.
    ttl: Callable[[Any], Duration]  # of the result: a fixed ttl is a function that returns it
    stale: Stale
    stampede: Stampede
    negative: Negative
    store: Store

    clock: Callable[[], float]

    @classmethod
    def of(
        cls,
        *,
        ttl: TTL,
        stale: Stale,
        stampede: Stampede,
        negative: Negative,
        store: Store,
        clock: Callable[[], float],
    ) -> Self:
        """The options a user gave a cached function, with the names of its arguments."""
        ttl = parse_ttl("ttl", ttl, _TTL_MEANING)
        validate_type("stale", stale, Stale)
        validate_type("stampede", stampede, Stampede)
        validate_type("negative", negative, Negative)
        validate_type("store", store, Store)

        policy = cls(
            ttl=ttl if callable(ttl) else lambda _result: ttl,
            stale=stale,
            stampede=stampede,
            negative=negative,
            store=store,
            clock=clock,
        )
        if ttl == 0 and policy.stale_seconds == 0:  # a function as ttl is never 0
            msg = "ttl is 0 and no Stale window is set, so no result would ever be stored: set either"
            raise InvalidOptionsError(msg)

        shortest = 0 if callable(ttl) else ttl * (1 - stampede.jitter)  # as jitter may spread it
        if 0 < shortest <= stampede.revalidate_before:
            msg = (
                f"Stampede.revalidate_before is {stampede.revalidate_before:g} and ttl is {ttl:g}: "
                "it reloads in the last seconds of the TTL, so it must be shorter, jitter counted"
            )
            raise InvalidOptionsError(msg)
        return policy

    @classmethod
    def of_batch(
        cls,
        *,
        ttl: TTL,
        stale: Stale,
        stampede: Stampede,
        store: Store,
        clock: Callable[[], float],
    ) -> Self:
        """The options of a batch function.

        It keeps no "not found", shares no loads and reloads nothing in the background.
        """
        policy = cls.of(ttl=ttl, stale=stale, stampede=stampede, negative=Negative(), store=store, clock=clock)
        refused = [
            name
            for name, given in (
                ("Stampede.lock_for", policy.stampede.lock_for),
                ("Stampede.revalidate_before", policy.stampede.revalidate_before),
                ("Stale.while_revalidate", policy.stale.while_revalidate),
                ("Stale.if_slow", policy.stale.if_slow),
            )
            if given
        ]
        if refused:
            names = ", ".join(refused)
            msg = f"a batch shares no loads, waits for its load and reloads nothing in the background: it takes no {names}"
            raise InvalidOptionsError(msg)
        return policy

    @property
    def stale_seconds(self) -> float:
        """How long past fresh a result may still answer: the longest window of Stale."""
        return max(self.stale.while_revalidate, self.stale.if_error, self.stale.if_slow)

    def add_jitter(self, seconds: float) -> float:
        jitter = self.stampede.jitter
        if jitter == 0 or seconds <= 0:
            return seconds
        return seconds * (1 + random.uniform(-jitter, jitter))  # noqa: S311 - jitter, not a secret

    def is_negative(self, error: Exception) -> bool:
        return isinstance(error, self.negative.on)  # an empty tuple of Negative() matches no error

    def should_store_loaded(self, result: object, load_seconds: float) -> bool:
        """A loaded result: only if its load took Store.slower_than at least."""
        return load_seconds >= self.store.slower_than and self.should_store(result)

    def should_store(self, result: object) -> bool:
        """A result set by hand: how long a load takes does not count."""
        return self.store.when is None or self.store.when(result)

    def freshness_lifetime(self, result: object) -> float | None:
        """None when no window would ever answer with the result; a negative ttl of the user raises."""
        fresh = duration_seconds(self.ttl(result))
        if fresh < 0:
            msg = f"ttl returned {fresh}; leave a result out with Store(when=...)"
            raise InvalidOptionsError(msg)
        if fresh + self.stale_seconds <= 0:
            return None
        return self.add_jitter(fresh)

    def negative_lifetime(self) -> float | None:
        """None when Negative keeps no "not found"."""
        return self.add_jitter(self.negative.ttl) if self.negative.on else None

    def storage_seconds(self, fresh_seconds: float) -> float:
        """How long the backend keeps a result: fresh, then its stale windows."""
        return fresh_seconds + self.stale_seconds

    def answer_for(
        self,
        stored: Stored | None,
        *,
        hit: CacheStatus = CacheStatus.HIT,
    ) -> Answer | None:
        """``hit``: the status of a fresh answer, FALLBACK for an entry of the fallback."""
        if stored is None:
            return None
        entry = stored.entry
        now = self.clock()
        if entry.negative:
            return Answer(None, CacheStatus.NOT_FOUND) if now < entry.stale_at else None
        if now < entry.stale_at:
            return Answer.of(stored, hit)
        if now < entry.stale_at + self.stale.while_revalidate:
            return Answer.of(stored, CacheStatus.STALE_WHILE_REVALIDATE)
        return None

    def should_revalidate(self, answer: Answer) -> bool:
        """Whether the answer is reloaded in the background.

        Stale while revalidate, or fresh in the last seconds of Stampede.revalidate_before.
        """
        if answer.status is CacheStatus.STALE_WHILE_REVALIDATE:
            return True
        ahead = self.stampede.revalidate_before
        due = answer.stale_at is not None and answer.stale_at - self.clock() < ahead
        return answer.status is CacheStatus.HIT and due

    def stale_windows(self, stored: Stored) -> StaleWindows:
        since = self.clock() - stored.entry.stale_at
        return StaleWindows(within_if_error=since < self.stale.if_error, within_if_slow=since < self.stale.if_slow)

    def stale_answer(
        self,
        stored: Stored,
        error: Exception,
        *,
        load_seconds: float,
        has_stale_answer: bool,
    ) -> Answer | None:
        """The stale result that answers instead of error, if a window of Stale lets it now.

        ``has_stale_answer``: the load skipped a full limit of loads, as this result could answer.
        """
        within_if_error, within_if_slow = self.stale_windows(stored)
        if isinstance(error, OverloadedError) and has_stale_answer:
            status = CacheStatus.STALE_IF_SLOW if within_if_slow else CacheStatus.STALE_IF_ERROR
            return Answer.of(stored, status, load_seconds)
        answers = isinstance(error, self.stale.if_error_on) and not self.is_negative(error)
        if within_if_error and answers and not isinstance(error, NotFoundError):
            return Answer.of(stored, CacheStatus.STALE_IF_ERROR, load_seconds)
        return None


@final
class StaleWindows(NamedTuple):
    # which windows of Stale a stale result is still inside, for the reload it waits on
    within_if_error: bool
    within_if_slow: bool
