"""Metrics and trace events of caches through OpenTelemetry: the opentelemetry extra.

The extra brings the API only, as OpenTelemetry asks of a library: the application sets up the SDK
and its exporters, and without them the instruments cost next to nothing. No semantic convention of
OpenTelemetry covers caches yet, so the names follow its general rules, under the pashe namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final, override

from pashe import __version__
from pashe._internal.checks import validate_type
from pashe.errors import MissingExtraError
from pashe.hooks import Hook

try:
    from opentelemetry import metrics, trace
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "opentelemetry", name=error.name) from error

if TYPE_CHECKING:
    from pashe.hooks import Circuit, Failure, NearRead, Outcome, RateLimitDecision

__all__ = ["OtelMetricsHook", "OtelSpanEventsHook"]

# What the HTTP conventions of OpenTelemetry advise for durations, and prometheus_client has by default.
_LOAD_BUCKETS: Final = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)


@final
class OtelMetricsHook(Hook):
    """A hook that records how cached calls are answered, how long loads take and the errors worked around.

    - ``pashe.calls``, a counter of ``{call}``: every cached call and item of a batch, by
      ``pashe.function`` and ``pashe.status``.
    - ``pashe.load.duration``, a histogram in ``s``: every run of a function for a call, by
      ``pashe.function``.
    - ``pashe.errors``, a counter of ``{error}``: every error a cache works around, by
      ``pashe.operation`` and ``error.type``, the qualified name of its class.
    - ``pashe.rate_limit.calls``, a counter of ``{call}``: every call a rate limit counted, by
      ``pashe.rate_limit.result``, ``allowed`` or ``refused``.
    - ``pashe.near.reads``, a counter of ``{read}``: every key a near cache given the hook read,
      by ``pashe.near.source``: ``local``, its copy answered, or ``shared``.
    - ``pashe.near.flushes``, a counter of ``{flush}``: every time such a near cache dropped
      every copy.
    - ``pashe.circuit.changes``, a counter of ``{change}``: every time a CircuitBreaker given the
      hook opened or closed, by ``pashe.circuit.state``, ``open`` or ``closed``.

    The key of a call is no attribute: each key would make series of its own. One hook may serve
    every cache of the application. Through the Prometheus exporter of OpenTelemetry the names read
    as PrometheusMetricsHook of pashe.contrib.prometheus writes them.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> from pashe.contrib.opentelemetry import OtelMetricsHook
        >>> cache = AsyncCache(AsyncMemoryBackend(), hooks=[OtelMetricsHook()])
    """

    __slots__ = ("_calls", "_circuit_changes", "_errors", "_flushes", "_loads", "_near_reads", "_rate_limit_calls")

    def __init__(self, *, meter: metrics.Meter | None = None) -> None:
        """Create the instruments.

        Args:
            meter: where to create them; by default the meter ``pashe`` of the global meter provider.

        Raises:
            TypeError: meter is not a Meter.
        """
        validate_type("meter", meter, metrics.Meter | None)
        made = meter or metrics.get_meter("pashe", __version__)

        self._calls = made.create_counter(
            "pashe.calls", unit="{call}", description="Cached calls and items of batches, by how they were answered."
        )
        self._loads = made.create_histogram(
            "pashe.load.duration",
            unit="s",
            description="Runs of functions for cached calls.",
            explicit_bucket_boundaries_advisory=_LOAD_BUCKETS,
        )
        self._errors = made.create_counter(
            "pashe.errors", unit="{error}", description="Errors caches worked around instead of raising them."
        )
        self._rate_limit_calls = made.create_counter(
            "pashe.rate_limit.calls",
            unit="{call}",
            description="Calls rate limits counted, by whether they went through.",
        )
        self._near_reads = made.create_counter(
            "pashe.near.reads", unit="{read}", description="Keys near caches read, by where they found them."
        )
        self._flushes = made.create_counter(
            "pashe.near.flushes", unit="{flush}", description="Times near caches dropped every copy."
        )
        self._circuit_changes = made.create_counter(
            "pashe.circuit.changes", unit="{change}", description="Times breakers of backends opened or closed."
        )

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        self._calls.add(1, {"pashe.function": outcome.function, "pashe.status": outcome.status.value})
        if outcome.load_seconds > 0:
            self._loads.record(outcome.load_seconds, {"pashe.function": outcome.function})

    @override
    def on_error(self, failure: Failure, /) -> None:
        self._errors.add(1, {"pashe.operation": failure.operation.value, "error.type": failure.error_type})

    @override
    def on_rate_limit(self, decision: RateLimitDecision, /) -> None:
        self._rate_limit_calls.add(1, {"pashe.rate_limit.result": decision.label})

    @override
    def on_near_read(self, read: NearRead, /) -> None:
        for source, count in read.sources.items():
            self._near_reads.add(count, {"pashe.near.source": source})

    @override
    def on_near_flush(self) -> None:
        self._flushes.add(1)

    @override
    def on_circuit(self, circuit: Circuit, /) -> None:
        self._circuit_changes.add(1, {"pashe.circuit.state": circuit.state})


@final
class OtelSpanEventsHook(Hook):
    """A hook that adds every cached call, and every error worked around, to the current span.

    A call becomes the event ``pashe.call``, with ``pashe.function``, ``pashe.key``,
    ``pashe.status`` and, for a stored result, ``pashe.fresh_seconds``. An error becomes an exception event
    with ``pashe.operation`` and ``pashe.key``; the span keeps its status, as the cache answered.
    The key goes into the trace: give the templates of keys that hold personal data a digest,
    such as ``{email:hmac}``. Without a span that records, the hook does nothing.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> from pashe.contrib.opentelemetry import OtelMetricsHook, OtelSpanEventsHook
        >>> cache = AsyncCache(AsyncMemoryBackend(), hooks=[OtelMetricsHook(), OtelSpanEventsHook()])
    """

    __slots__ = ()

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        span = trace.get_current_span()
        if not span.is_recording():
            return
        attributes: dict[str, str | float] = {
            "pashe.function": outcome.function,
            "pashe.key": outcome.key,
            "pashe.status": outcome.status.value,
        }
        if outcome.fresh_seconds is not None:
            attributes["pashe.fresh_seconds"] = outcome.fresh_seconds
        span.add_event("pashe.call", attributes)

    @override
    def on_error(self, failure: Failure, /) -> None:
        span = trace.get_current_span()
        if span.is_recording():
            span.record_exception(failure.error, {"pashe.operation": failure.operation.value, "pashe.key": failure.key})
