"""The benchmarks of pashe: ``just bench`` measures them, every other run of pytest runs each once as a test."""

from __future__ import annotations

from typing import Protocol

import pytest

pytest_plugins = ["tests.harness.servers"]  # Redis in Docker, as the tests start it

_BYTES = pytest.StashKey[dict[str, tuple[int, int | None]]]()  # a benchmark: the bytes it made, of how many


class RecordBytes(Protocol):
    def __call__(self, made: int, /, given: int | None = None) -> None: ...


def pytest_configure(config: pytest.Config) -> None:
    config.stash[_BYTES] = {}


@pytest.fixture
def record_bytes(request: pytest.FixtureRequest) -> RecordBytes:
    """Keep the bytes a benchmark made, of those it was given if any, for the table after the times."""
    recorded = request.config.stash[_BYTES]

    def record(made: int, /, given: int | None = None) -> None:
        recorded[request.node.name] = (made, given)

    return record


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    recorded = config.stash[_BYTES]
    measured = config.getoption("benchmark_enable") or not config.getoption("benchmark_disable")
    if not (measured and recorded):
        return  # a run of the tests, which takes each benchmark once
    terminalreporter.section("bytes")
    for name, (made, given) in sorted(recorded.items()):
        of_given = "" if given is None else f" of {given:>9,}: {made / given:6.1%}"
        terminalreporter.write_line(f"{name:<64} {made:>9,}{of_given}")
