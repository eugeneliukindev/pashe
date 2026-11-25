from __future__ import annotations

from typing import TYPE_CHECKING, final

from pashe.errors import CodecError, InvalidOptionsError
from pashe.hooks import Failure, Operation

if TYPE_CHECKING:
    from pashe._internal.cache.call import CallState
    from pashe._internal.cache.entry import EntryFormat, Generations, Stored
    from pashe._internal.cache.policy import Policy
    from pashe.hooks import Hook


@final
class EntryCodec:
    # The entries of one cached function: its policy decides what is stored and for how long, its
    # format encodes, and what fails on the way goes to the hooks, as a miss, not an error.
    __slots__ = ("_format", "_hooks", "_policy")

    def __init__(self, policy: Policy, entry_format: EntryFormat, hooks: Hook) -> None:
        self._policy = policy
        self._format = entry_format
        self._hooks = hooks

    def encode_loaded(self, state: CallState, value: object) -> Stored | None:
        if not self._policy.should_store_loaded(value, state.load_seconds):
            return None
        return self._encode(state, value)

    def encode(self, state: CallState, value: object) -> Stored | None:
        if not self._policy.should_store(value):
            return None
        return self._encode(state, value)

    def encode_negative(self, state: CallState) -> Stored | None:
        lifetime = self._policy.negative_lifetime()
        if lifetime is None:
            return None
        stale_at = self._policy.clock() + lifetime
        return self._format.encode_negative(
            stale_at=stale_at, fresh_for=lifetime, tag_generations=state.tag_generations
        )

    def decode(self, key: str, raw: bytes | None, tag_generations: Generations) -> Stored | None:
        # None for no entry, one stored as another type, or one a tag invalidated after it was stored
        if raw is None:
            return None
        try:
            stored = self._format.decode(raw)
        except CodecError as error:
            self._hooks.on_error(Failure(Operation.DECODE, key, error))
            return None
        if stored is None or stored.entry.tag_generations != tag_generations:
            return None
        return stored

    def _encode(self, state: CallState, value: object) -> Stored | None:
        try:
            lifetime = self._policy.freshness_lifetime(value)
        except InvalidOptionsError as error:  # a ttl of the result that is negative
            self._hooks.on_error(Failure(Operation.TTL, state.key, error))
            return None
        if lifetime is None:
            return None
        stale_at = self._policy.clock() + lifetime
        try:
            return self._format.encode(
                value, stale_at=stale_at, fresh_for=lifetime, tag_generations=state.tag_generations
            )
        except CodecError as error:
            self._hooks.on_error(Failure(Operation.ENCODE, state.key, error))
            return None
