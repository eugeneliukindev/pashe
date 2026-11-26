from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from pashe._internal.checks import expect_item_types, expect_type
from pashe.hooks import Hook

if TYPE_CHECKING:
    from pashe.hooks import Circuit, Failure, NearRead, Outcome, RateLimitDecision


@final
class Hooks(Hook):
    __slots__ = ("_hooks",)

    def __init__(self, hooks: list[Hook] | tuple[Hook, ...]) -> None:
        # the hooks argument of a public class, checked here, where every one of them comes in
        expect_type("hooks", hooks, list | tuple)  # pyrefly: ignore[implicit-any-type-argument] - isinstance takes it bare
        expect_item_types("hooks", hooks, Hook)

        self._hooks = tuple(hooks)

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
