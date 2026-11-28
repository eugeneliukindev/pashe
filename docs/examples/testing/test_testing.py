from __future__ import annotations

import importlib

import pytest
from tests.harness.helpers import call


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_the_test_of_the_page_passes(side: str) -> None:
    example = importlib.import_module(f"examples.testing.loaded_once_{side}")

    await call(example.test_a_user_is_loaded_once)
