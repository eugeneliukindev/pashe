from __future__ import annotations

import importlib

import pytest
from tests.harness.helpers import call


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_a_cached_result_keeps_the_bytes_the_page_shows(side: str) -> None:
    example = importlib.import_module(f"examples.storage.cached_result_{side}")
    await call(example.get_user, 1)

    raw = await call(example.backend.get, "shop:user:1")

    assert raw is not None
    assert len(raw) == 49
    assert raw.endswith(b'{"id":1,"name":"Ada"}')
