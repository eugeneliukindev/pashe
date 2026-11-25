from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from pashe.hooks import Hook

if TYPE_CHECKING:
    from pashe.hooks import Circuit, Failure, NearRead, Outcome, RateLimitDecision


@final
class AllHooks(Hook):
    __slots__ = ("_hooks",)

    def __init__(self, hooks: tuple[Hook, ...]) -> None:
        self._hooks = hooks

    def __bool__(self) -> bool:
        # whether any hook listens: a caller with nothing to tell skips making the event
        return bool(self._hooks)

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        for hook in self._hooks:
            hook.on_call(outcome)

    @override
    def on_error(self, failure: Failure, /) -> None:
        for hook in self._hooks:
            hook.on_error(failure)

    @override
    def on_rate_limit(self, decision: RateLimitDecision, /) -> None:
        for hook in self._hooks:
            hook.on_rate_limit(decision)

    @override
    def on_near_read(self, read: NearRead, /) -> None:
        for hook in self._hooks:
            hook.on_near_read(read)

    @override
    def on_near_flush(self) -> None:
        for hook in self._hooks:
            hook.on_near_flush()

    @override
    def on_circuit(self, circuit: Circuit, /) -> None:
        for hook in self._hooks:
            hook.on_circuit(circuit)
