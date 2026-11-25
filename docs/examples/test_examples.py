"""Every example of the docs imports, and the calls it shows run."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from tests.harness.helpers import call

_ROOT = Path(__file__).parent
_EXAMPLES = sorted(path for path in _ROOT.glob("*/*.py") if not path.name.startswith(("test_", "_")))
# Their calls reach Redis at the address the page gives: they import, and the type checkers read the calls.
_REACH_REDIS = frozenset(
    ("backends/cluster_sync", "backends/cluster_async", "index/quick_start_sync", "index/quick_start_async")
)


def _name(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"


@pytest.mark.parametrize("path", _EXAMPLES, ids=_name)
def test_an_example_imports(path: Path) -> None:
    module = f"examples.{path.parent.name}.{path.stem}"

    importlib.import_module(module)


@pytest.mark.parametrize(
    "path",
    [path for path in _EXAMPLES if "def main(" in path.read_text() and _name(path) not in _REACH_REDIS],
    ids=_name,
)
async def test_the_calls_of_an_example_run(path: Path) -> None:
    example = importlib.import_module(f"examples.{path.parent.name}.{path.stem}")

    await call(example.main)
