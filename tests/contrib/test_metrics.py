"""The metrics of OpenTelemetry and of Prometheus, the same scenario read from each, and the events of spans."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import HistogramDataPoint, InMemoryMetricReader, NumberDataPoint
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry

from pashe import Cache
from pashe.backends import CircuitBreaker, MemoryBackend, NearCacheBackend
from pashe.contrib.opentelemetry import OtelMetricsHook, OtelSpanEventsHook
from pashe.contrib.prometheus import PrometheusMetricsHook
from pashe.errors import RateLimitedError
from pashe.ratelimit import FixedWindow
from tests.harness.helpers import Clock, FailingMemoryBackend, MemoryBus

if TYPE_CHECKING:
    from pashe.hooks import Hook

_ERROR_TYPE = "pashe.errors.BackendError"


def _rate() -> float:
    return 0.92


_FUNCTION = f"{_rate.__module__}.{_rate.__qualname__}"


def _scenario(hook: Hook) -> None:
    # A miss, a hit, and a miss whose read fails; a call a limit lets through and one it refuses.
    backend = FailingMemoryBackend()
    cache = Cache(backend, hooks=[hook])
    get_rate = cache(ttl=60)(_rate)
    get_rate()
    get_rate()
    limit = FixedWindow(calls=1, per=60, ban_for=60)
    cache.rate_limit("ip", limit)
    with contextlib.suppress(RateLimitedError):
        cache.rate_limit("ip", limit)
    backend.down = True
    get_rate()

    # Two keys read from the shared backend and one from a copy, then every copy dropped.
    wire = MemoryBus()
    near = NearCacheBackend(MemoryBackend(), MemoryBackend(), bus=wire, hooks=[hook])
    near.set("k", b"v")
    near.get_many(["k", "missing"])
    near.get("k")
    wire.publish(None)

    # A breaker opened by a failure, then closed by the probe that answered.
    clock = Clock()
    breaker = CircuitBreaker(failure_threshold=1, open_for=10, hooks=[hook], clock=clock)
    breaker.on_failure()
    clock.now += 10
    breaker.before_call()
    breaker.on_success()


def test_otel_metrics_count_calls_loads_and_errors() -> None:
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader]).get_meter("test")

    _scenario(OtelMetricsHook(meter=meter))

    data = reader.get_metrics_data()
    assert data is not None
    points: dict[tuple[str, frozenset[tuple[str, object]]], float] = {}
    for metric in data.resource_metrics[0].scope_metrics[0].metrics:
        for point in metric.data.data_points:
            assert isinstance(point, HistogramDataPoint | NumberDataPoint)
            value = point.count if isinstance(point, HistogramDataPoint) else point.value
            points[metric.name, frozenset((point.attributes or {}).items())] = value
    assert points == {
        ("pashe.calls", frozenset({("pashe.function", _FUNCTION), ("pashe.status", "miss")})): 2,
        ("pashe.calls", frozenset({("pashe.function", _FUNCTION), ("pashe.status", "hit")})): 1,
        ("pashe.load.duration", frozenset({("pashe.function", _FUNCTION)})): 2,
        ("pashe.errors", frozenset({("pashe.operation", "get"), ("error.type", _ERROR_TYPE)})): 1,
        ("pashe.rate_limit.calls", frozenset({("pashe.rate_limit.result", "allowed")})): 1,
        ("pashe.rate_limit.calls", frozenset({("pashe.rate_limit.result", "refused")})): 1,
        ("pashe.near.reads", frozenset({("pashe.near.source", "shared")})): 2,
        ("pashe.near.reads", frozenset({("pashe.near.source", "local")})): 1,
        ("pashe.near.flushes", frozenset()): 1,
        ("pashe.circuit.changes", frozenset({("pashe.circuit.state", "open")})): 1,
        ("pashe.circuit.changes", frozenset({("pashe.circuit.state", "closed")})): 1,
    }


def test_prometheus_metrics_count_calls_loads_and_errors() -> None:
    registry = CollectorRegistry()

    _scenario(PrometheusMetricsHook(registry=registry))

    def sample(name: str, **labels: str) -> float | None:
        return registry.get_sample_value(name, labels)

    assert sample("pashe_calls_total", pashe_function=_FUNCTION, pashe_status="miss") == 2
    assert sample("pashe_calls_total", pashe_function=_FUNCTION, pashe_status="hit") == 1
    assert sample("pashe_load_duration_seconds_count", pashe_function=_FUNCTION) == 2
    assert sample("pashe_errors_total", pashe_operation="get", error_type=_ERROR_TYPE) == 1
    assert sample("pashe_rate_limit_calls_total", pashe_rate_limit_result="allowed") == 1
    assert sample("pashe_rate_limit_calls_total", pashe_rate_limit_result="refused") == 1
    assert sample("pashe_near_reads_total", pashe_near_source="shared") == 2
    assert sample("pashe_near_reads_total", pashe_near_source="local") == 1
    assert sample("pashe_near_flushes_total") == 1
    assert sample("pashe_circuit_changes_total", pashe_circuit_state="open") == 1
    assert sample("pashe_circuit_changes_total", pashe_circuit_state="closed") == 1


def test_otel_span_events_tell_the_span_of_calls_and_errors(clock: Clock) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    backend = FailingMemoryBackend()
    get_rate = Cache(backend, hooks=[OtelSpanEventsHook()], clock=clock)(ttl=60, key="rate")(_rate)

    with provider.get_tracer("test").start_as_current_span("request"):
        get_rate()
        backend.down = True
        get_rate()  # the read fails: the loader answers, and nothing is stored

    (span,) = exporter.get_finished_spans()
    events = [(event.name, dict(event.attributes or {})) for event in span.events]
    call = {"pashe.function": _FUNCTION, "pashe.key": "rate", "pashe.status": "miss"}
    assert events[0] == ("pashe.call", call | {"pashe.fresh_for": 60.0})
    assert events[1][0] == "exception"
    assert events[1][1]["exception.type"] == _ERROR_TYPE
    assert (events[1][1]["pashe.operation"], events[1][1]["pashe.key"]) == ("get", "rate")
    assert events[2] == ("pashe.call", call)
