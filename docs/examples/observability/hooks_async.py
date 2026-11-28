# ruff: noqa: E402 - the page shows these imports after what it leaves out
# --8<-- [start:show]
from __future__ import annotations

from typing import TYPE_CHECKING

from pashe.backends import AsyncMemoryBackend
from pashe.hooks import Outcome

if TYPE_CHECKING:
    from pashe.hooks import Failure

backend = AsyncMemoryBackend()


outcomes: list[Outcome] = []
failures: list[Failure] = []
record_outcome = outcomes.append
log_failure = failures.append


from typing import override

from pashe import AsyncCache
from pashe.hooks import Failure, Hook


class Metrics(Hook):
    @override
    def on_call(self, outcome: Outcome, /) -> None:
        record_outcome(outcome)  # such as a counter by outcome.function and outcome.status

    @override
    def on_error(self, failure: Failure, /) -> None:
        log_failure(failure)  # failure.operation, failure.key and failure.error


cache = AsyncCache(backend, hooks=[Metrics()])
# --8<-- [end:show]
