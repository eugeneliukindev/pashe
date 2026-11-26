from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, NamedTuple, Self, final

from pashe._internal.cache.call import Answer
from pashe._internal.checks import duration_seconds, expect_type, parse_ttl
from pashe.errors import InvalidOptionsError, NotFoundError, OverloadedError
from pashe.hooks import CacheStatus
from pashe.options import IfError, Negative, Stale, Stampede, Store

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
    stale: StalePolicy
    stampede: StampedePolicy
    negative: NegativePolicy
    store: StorePolicy

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
        # the options a user gave a cached function, with the names of its arguments
        ttl = parse_ttl("ttl", ttl, _TTL_MEANING)
        expect_type("stale", stale, Stale)
        expect_type("stampede", stampede, Stampede)
        expect_type("negative", negative, Negative)
        expect_type("store", store, Store)

        stale_policy = StalePolicy.of(stale)
        if ttl == 0 and stale_policy.longest_window == 0:  # a function as ttl is never 0
            msg = "ttl is 0 and no Stale window is set, so no result would ever be stored: set either"
            raise InvalidOptionsError(msg)

        stampede_policy = StampedePolicy.of(stampede)
        shortest = 0 if callable(ttl) else ttl * (1 - stampede_policy.jitter)  # as jitter may spread it
        if 0 < shortest <= stampede_policy.revalidate_before:
            msg = (
                f"Stampede.revalidate_before is {stampede.revalidate_before!r} and ttl is {ttl}: "
                "it reloads in the last seconds of the TTL, so it must be shorter, jitter counted"
            )
            raise InvalidOptionsError(msg)

        return cls(
            ttl=ttl if callable(ttl) else lambda _result: ttl,
            stale=stale_policy,
            stampede=stampede_policy,
            negative=NegativePolicy.of(negative),
            store=StorePolicy.of(store),
            clock=clock,
        )

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
        # the options of a batch function: it keeps no "not found", shares no loads and reloads nothing in the background
        policy = cls.of(ttl=ttl, stale=stale, stampede=stampede, negative=Negative(), store=store, clock=clock)
        refused = [
            name
            for name, given in (
                ("Stampede.lock_for", policy.stampede.lock_for),
                ("Stampede.revalidate_before", policy.stampede.revalidate_before),
                ("Stale.while_revalidate", policy.stale.while_revalidate),
                ("Stale.if_slow", policy.stale.slow_after),
            )
            if given
        ]
        if refused:
            names = ", ".join(refused)
            msg = f"a batch shares no loads, waits for its load and reloads nothing in the background: it takes no {names}"
            raise InvalidOptionsError(msg)
        return policy

    def add_jitter(self, seconds: float) -> float:
        jitter = self.stampede.jitter
        if jitter == 0 or seconds <= 0:
            return seconds
        return seconds * (1 + random.uniform(-jitter, jitter))  # noqa: S311 - jitter, not a secret

    def is_negative(self, error: Exception) -> bool:
        return isinstance(error, self.negative.on)  # an empty tuple of Negative() matches no error

    def should_store_loaded(self, result: object, load_seconds: float) -> bool:
        # a loaded result: only if its load took Store.slower_than at least
        return load_seconds >= self.store.slower_than and self.should_store(result)

    def should_store(self, result: object) -> bool:
        # a result set by hand: how long a load takes does not count
        return self.store.when is None or self.store.when(result)

    def freshness_lifetime(self, result: object) -> float | None:
        # None when no window would ever answer with the result; a negative ttl of the user raises
        fresh = duration_seconds(self.ttl(result))
        if fresh < 0:
            msg = f"ttl returned {fresh}; leave a result out with Store(when=...)"
            raise InvalidOptionsError(msg)
        if fresh + self.stale.longest_window <= 0:
            return None
        return self.add_jitter(fresh)

    def negative_lifetime(self) -> float | None:
        # None when Negative keeps no "not found"
        return self.add_jitter(self.negative.ttl) if self.negative.on else None

    def storage_seconds(self, fresh_seconds: float) -> float:
        # how long the backend keeps a result: fresh, then its stale windows
        return fresh_seconds + self.stale.longest_window

    def answer_for(self, stored: Stored | None) -> Answer | None:
        if stored is None:
            return None
        entry = stored.entry
        now = self.clock()
        if entry.negative:
            return Answer(None, CacheStatus.NOT_FOUND) if now < entry.stale_at else None
        if now < entry.stale_at:
            return Answer.of(stored, CacheStatus.HIT)
        if now < entry.stale_at + self.stale.while_revalidate:
            return Answer.of(stored, CacheStatus.STALE_WHILE_REVALIDATE)
        return None

    def should_revalidate(self, answer: Answer) -> bool:
        # whether the answer is reloaded in the background: stale while revalidate, or fresh in
        # the last seconds of Stampede.revalidate_before
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
        # The stale result that answers instead of error, if a window of Stale lets it now;
        # has_stale_answer: the load skipped a full limit of loads, as this result could answer.
        within_if_error, within_if_slow = self.stale_windows(stored)
        if isinstance(error, OverloadedError) and has_stale_answer:
            status = CacheStatus.STALE_IF_SLOW if within_if_slow else CacheStatus.STALE_IF_ERROR
            return Answer.of(stored, status, load_seconds)
        answers = isinstance(error, self.stale.if_error_on) and not self.is_negative(error)
        if within_if_error and answers and not isinstance(error, NotFoundError):
            return Answer.of(stored, CacheStatus.STALE_IF_ERROR, load_seconds)
        return None


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class StalePolicy:
    # Stale with its windows in seconds
    while_revalidate: float
    if_error: float
    if_error_on: tuple[type[Exception], ...]
    if_slow: float
    slow_after: float  # 0 exactly when if_slow is off

    @classmethod
    def of(cls, stale: Stale) -> Self:
        # Stale checked its windows: here they only turn into seconds
        if_error = stale.if_error if isinstance(stale.if_error, IfError) else IfError(stale.if_error)
        if_slow = stale.if_slow
        return cls(
            while_revalidate=duration_seconds(stale.while_revalidate),
            if_error=duration_seconds(if_error.window),
            if_error_on=if_error.on,
            if_slow=0 if if_slow is None else duration_seconds(if_slow.window),
            slow_after=0 if if_slow is None else duration_seconds(if_slow.after),
        )

    @property
    def longest_window(self) -> float:
        # how long past fresh a result may still answer
        return max(self.while_revalidate, self.if_error, self.if_slow)


@final
class StaleWindows(NamedTuple):
    # which windows of Stale a stale result is still inside, for the reload it waits on
    within_if_error: bool
    within_if_slow: bool


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class StampedePolicy:
    # Stampede with revalidate_before and lock_for in seconds
    revalidate_before: float
    lock_for: float
    jitter: float
    max_loads: int  # 0 means no limit
    share_loads: bool

    @classmethod
    def of(cls, stampede: Stampede) -> Self:
        return cls(
            revalidate_before=duration_seconds(stampede.revalidate_before),
            lock_for=duration_seconds(stampede.lock_for),
            jitter=stampede.jitter,
            max_loads=stampede.max_loads,
            share_loads=stampede.share_loads,
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class NegativePolicy:
    # Negative with its ttl in seconds
    on: tuple[type[Exception], ...]
    ttl: float

    @classmethod
    def of(cls, negative: Negative) -> Self:
        return cls(on=negative.on, ttl=duration_seconds(negative.ttl))


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class StorePolicy:
    # Store with slower_than in seconds
    when: Callable[[Any], bool] | None
    slower_than: float

    @classmethod
    def of(cls, store: Store) -> Self:
        return cls(when=store.when, slower_than=duration_seconds(store.slower_than))
