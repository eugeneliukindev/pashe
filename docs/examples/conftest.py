from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def fresh_examples(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make every test import the examples anew, so their caches start empty, and close what they opened."""
    for name in [name for name in sys.modules if name.startswith("examples.")]:
        monkeypatch.delitem(sys.modules, name)

    yield

    for name, module in list(sys.modules.items()):
        close = getattr(module, "close", None) if name.startswith("examples.") else None
        if callable(close):
            close()
