"""Errors of caches in Sentry through sentry_sdk: the sentry extra."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final, override

from pashe._internal.checks import expect_type
from pashe.errors import MissingExtraError
from pashe.hooks import Hook

try:
    import sentry_sdk
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "sentry", name=error.name) from error

if TYPE_CHECKING:
    from pashe.hooks import Circuit, Failure

__all__ = ["SentryHook"]

_CATEGORY: Final = "pashe"


@final
class SentryHook(Hook):
    """A hook that leaves every error a cache works around as a breadcrumb in Sentry.

    Such an error, as a backend that is down, raises nothing: the call is answered all the
    same. As a breadcrumb it shows in the next event the application sends, such as the error of
    a request, with ``pashe.operation`` and ``error.type``. The key is left out, as it may name
    a user. A CircuitBreaker given the hook leaves a breadcrumb when it opens and closes. Call
    sentry_sdk.init as you would without it.

    Examples:
        >>> from pashe import Cache
        >>> from pashe.backends import MemoryBackend
        >>> from pashe.contrib.sentry import SentryHook
        >>> cache = Cache(MemoryBackend(), hooks=[SentryHook()])
    """

    __slots__ = ("_capture_errors",)

    def __init__(self, *, capture_errors: bool = False) -> None:
        """Create the hook.

        Args:
            capture_errors: send every such error as an event of its own too, with the tag
                ``pashe.operation`` and the text of the error; off by default, as a backend that is
                down would send one per call.

        Raises:
            TypeError: capture_errors is not a bool.
        """
        expect_type("capture_errors", capture_errors, bool)

        self._capture_errors = capture_errors

    @override
    def on_error(self, failure: Failure, /) -> None:
        sentry_sdk.add_breadcrumb(
            category=_CATEGORY,
            level="warning",
            message=f"{failure.operation}: {failure.error_type}",  # not its text, which may name the key
            data={"pashe.operation": failure.operation.value, "error.type": failure.error_type},
        )
        if self._capture_errors:
            sentry_sdk.capture_exception(failure.error, tags={"pashe.operation": failure.operation.value})

    @override
    def on_circuit(self, circuit: Circuit, /) -> None:
        sentry_sdk.add_breadcrumb(
            category=_CATEGORY,
            level="warning" if circuit.open else "info",
            message=f"the breaker of a backend is {circuit.state}",
            data={"pashe.circuit.state": circuit.state, "failures": circuit.failures},
        )
