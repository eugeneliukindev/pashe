from __future__ import annotations

import importlib

import pytest
from tests.harness.helpers import call, recording_calls


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_a_cached_function_loads_once_and_its_methods_do_what_they_say(
    side: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    example = importlib.import_module(f"examples.getting_started.function_{side}")
    loads: list[tuple[object, ...]] = []
    monkeypatch.setattr(example, "load_user", recording_calls(example.load_user, loads))

    await call(example.main)  # two calls, then refresh, set and invalidate
    after_invalidate = await call(example.get_user, 1)

    assert loads == [(1,), (1,), (1,)]  # the first call, refresh, and the call after invalidate
    assert after_invalidate == {"id": "1", "name": "Ann"}
