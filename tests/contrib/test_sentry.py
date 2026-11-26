"""SentryHook: what a cache leaves in Sentry of the errors it works around."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

from pashe import Cache
from pashe.backends import CircuitBreaker
from pashe.contrib.sentry import SentryHook
from tests.harness.helpers import FailingMemoryBackend

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sentry_sdk._types import Event
    from sentry_sdk.envelope import Envelope


class _Sent(Transport):
    """A transport that keeps the events instead of sending them."""

    def __init__(self) -> None:
        super().__init__()

        self.events: list[Event] = []

    @override
    def capture_envelope(self, envelope: Envelope) -> None:
        self.events += [event for item in envelope.items if (event := item.get_event()) is not None]


@pytest.fixture
def sent() -> Iterator[_Sent]:
    transport = _Sent()
    # no integration patches Starlette or httpx for every later test of the process: the hook needs none
    sentry_sdk.init(
        dsn="https://key@example.invalid/1",
        transport=transport,
        default_integrations=False,
        auto_enabling_integrations=False,
    )
    with sentry_sdk.isolation_scope():
        yield transport
    sentry_sdk.init(
        default_integrations=False, auto_enabling_integrations=False
    )  # no client: the next test sends nothing


def _call_while_the_backend_is_down(hook: SentryHook) -> None:
    backend = FailingMemoryBackend()
    backend.down = True
    cache = Cache(backend, hooks=[hook])

    @cache(ttl=60, key="user:ada@example.com")
    def get_user() -> int:
        return 1

    get_user()


def _pashe_breadcrumbs(event: Event) -> list[dict[str, Any]]:
    breadcrumbs = event.get("breadcrumbs")
    assert isinstance(breadcrumbs, dict)  # an event read back from JSON: present, and never an AnnotatedValue
    return [crumb for crumb in breadcrumbs["values"] if crumb["category"] == "pashe"]


def test_an_error_the_cache_worked_around_is_a_breadcrumb_of_the_next_event(sent: _Sent) -> None:
    _call_while_the_backend_is_down(SentryHook())

    sentry_sdk.capture_message("the request failed")
    sentry_sdk.flush()

    [event] = sent.events
    first = _pashe_breadcrumbs(event)[0]
    assert first["data"] == {"pashe.operation": "get", "error.type": "pashe.errors.BackendError"}
    assert "ada@example.com" not in str(event.get("breadcrumbs"))  # the key may name a user


def test_capture_errors_sends_each_as_an_event_of_its_own(sent: _Sent) -> None:
    _call_while_the_backend_is_down(SentryHook(capture_errors=True))

    sentry_sdk.flush()

    assert {event.get("tags", {}).get("pashe.operation") for event in sent.events} >= {"get"}


def test_a_breaker_that_opened_is_a_breadcrumb_of_the_next_event(sent: _Sent) -> None:
    breaker = CircuitBreaker(failure_threshold=1, hooks=[SentryHook()])

    breaker.on_failure()
    sentry_sdk.capture_message("the request failed")
    sentry_sdk.flush()

    [event] = sent.events
    [crumb] = _pashe_breadcrumbs(event)
    assert (crumb["level"], crumb["data"]) == ("warning", {"pashe.circuit.state": "open", "failures": 1})
