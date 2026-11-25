"""Metrics of caches through prometheus_client: the prometheus extra.

The names and labels are those the Prometheus exporter of OpenTelemetry makes of OtelMetricsHook in
pashe.contrib.opentelemetry, so a dashboard reads either.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from pashe._internal.checks import expect_type
from pashe.errors import MissingExtraError
from pashe.hooks import Hook

try:
    import prometheus_client
except ModuleNotFoundError as error:
    raise MissingExtraError(__name__, "prometheus", name=error.name) from error

if TYPE_CHECKING:
    from pashe.hooks import Circuit, Failure, NearRead, Outcome, RateLimitDecision

__all__ = ["PrometheusMetricsHook"]


@final
class PrometheusMetricsHook(Hook):
    """A hook that counts how cached calls are answered, how long loads take and the errors worked around.

    - ``pashe_calls_total``: every cached call and item of a batch, by ``pashe_function`` and
      ``pashe_status``.
    - ``pashe_load_duration_seconds``, a histogram with the default buckets of prometheus_client:
      every run of a loader for a call, by ``pashe_function``.
    - ``pashe_errors_total``: every error a cache works around, by ``pashe_operation`` and
      ``error_type``, the qualified name of its class.
    - ``pashe_rate_limit_calls_total``: every call a rate limit counted, by
      ``pashe_rate_limit_result``, ``allowed`` or ``refused``.
    - ``pashe_near_reads_total``: every key a near cache given the hook read, by
      ``pashe_near_source``: ``local``, its copy answered, or ``shared``.
    - ``pashe_near_flushes_total``: every time such a near cache dropped every copy.
    - ``pashe_circuit_changes_total``: every time a CircuitBreaker given the hook opened or closed,
      by ``pashe_circuit_state``, ``open`` or ``closed``.

    The key of a call is no label: each key would make series of its own. Make one hook per
    registry and give it to every cache: a second one over the same registry raises ValueError
    of prometheus_client, as its metrics are there already.

    Examples:
        >>> from pashe import AsyncCache
        >>> from pashe.backends import AsyncMemoryBackend
        >>> from pashe.contrib.prometheus import PrometheusMetricsHook
        >>> from prometheus_client import CollectorRegistry
        >>> cache = AsyncCache(AsyncMemoryBackend(), hooks=[PrometheusMetricsHook(registry=CollectorRegistry())])
    """

    __slots__ = ("_calls", "_circuit_changes", "_errors", "_flushes", "_loads", "_near_reads", "_rate_limit_calls")

    def __init__(self, *, registry: prometheus_client.CollectorRegistry = prometheus_client.REGISTRY) -> None:
        """Register the metrics.

        Args:
            registry: where to register them; the global registry of prometheus_client by default.

        Raises:
            TypeError: registry is not a CollectorRegistry.
        """
        expect_type("registry", registry, prometheus_client.CollectorRegistry)

        self._calls = prometheus_client.Counter(
            "pashe_calls",
            "Cached calls and items of batches, by how they were answered.",
            ("pashe_function", "pashe_status"),
            registry=registry,
        )
        self._loads = prometheus_client.Histogram(
            "pashe_load_duration_seconds", "Runs of loaders for cached calls.", ("pashe_function",), registry=registry
        )
        self._errors = prometheus_client.Counter(
            "pashe_errors",
            "Errors caches worked around instead of raising them.",
            ("pashe_operation", "error_type"),
            registry=registry,
        )
        self._rate_limit_calls = prometheus_client.Counter(
            "pashe_rate_limit_calls",
            "Calls rate limits counted, by whether they went through.",
            ("pashe_rate_limit_result",),
            registry=registry,
        )
        self._near_reads = prometheus_client.Counter(
            "pashe_near_reads",
            "Keys near caches read, by where they found them.",
            ("pashe_near_source",),
            registry=registry,
        )
        self._flushes = prometheus_client.Counter(
            "pashe_near_flushes", "Times near caches dropped every copy.", registry=registry
        )
        self._circuit_changes = prometheus_client.Counter(
            "pashe_circuit_changes",
            "Times breakers of backends opened or closed.",
            ("pashe_circuit_state",),
            registry=registry,
        )

    @override
    def on_call(self, outcome: Outcome, /) -> None:
        self._calls.labels(outcome.function, outcome.status.value).inc()
        if outcome.load_seconds > 0:
            self._loads.labels(outcome.function).observe(outcome.load_seconds)

    @override
    def on_error(self, failure: Failure, /) -> None:
        self._errors.labels(failure.operation.value, failure.error_type).inc()

    @override
    def on_rate_limit(self, decision: RateLimitDecision, /) -> None:
        self._rate_limit_calls.labels(decision.label).inc()

    @override
    def on_near_read(self, read: NearRead, /) -> None:
        for source, count in read.sources.items():
            self._near_reads.labels(source).inc(count)

    @override
    def on_near_flush(self) -> None:
        self._flushes.inc()

    @override
    def on_circuit(self, circuit: Circuit, /) -> None:
        self._circuit_changes.labels(circuit.state).inc()
