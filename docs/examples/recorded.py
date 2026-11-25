"""A hook that keeps how every call was answered, for the tests of the pages; the pages leave it out."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from pashe.hooks import Hook

if TYPE_CHECKING:
    from pashe.hooks import Outcome


class Record(Hook):
    def __init__(self, outcomes: list[Outcome]) -> None:
        self.outcomes = outcomes

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        self.outcomes.append(outcome)
