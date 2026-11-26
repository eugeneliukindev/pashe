"""Every example of the docs imports, and the calls it shows run."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest
from tests.harness.helpers import call

from pashe import AsyncCache, Cache

_ROOT = Path(__file__).parent
_EXAMPLES = sorted(path for path in _ROOT.glob("*/*.py") if not path.name.startswith(("test_", "_")))
# Their calls reach Redis at the address the page gives: they import, and the type checkers read the calls.
_REACH_REDIS = frozenset(
    ("backends/cluster_sync", "backends/cluster_async", "index/quick_start_sync", "index/quick_start_async")
)
_OPTION_MODULES = ("pashe.options", "pashe.ratelimit")  # whose classes an example of every option spells out
_OPTIONS = sorted(
    _ROOT.glob("*/*_options_*.py")
)  # the "Every option" block of a page: a call of a cache with all it takes


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


@pytest.mark.parametrize("path", _OPTIONS, ids=_name)
def test_an_example_of_every_option_passes_every_option(path: Path) -> None:
    example = importlib.import_module(f"examples.{path.parent.name}.{path.stem}")
    cache_class = AsyncCache if path.stem.endswith("_async") else Cache
    shown: dict[str, tuple[object, int, set[str | None]]] = {}
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "cache":
            called: object = cache_class.__call__
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "cache"
        ):
            called = getattr(cache_class, node.func.attr)
        elif (
            isinstance(node.func, ast.Name)
            and getattr(getattr(example, node.func.id, None), "__module__", None) in _OPTION_MODULES
        ):
            called = getattr(example, node.func.id)
        else:
            continue
        shown[ast.unparse(node.func)] = (called, len(node.args), {keyword.arg for keyword in node.keywords})

    assert shown
    for name, (called, positional, named) in shown.items():
        parameters = [
            parameter.name
            for parameter in inspect.signature(called).parameters.values()  # type: ignore[arg-type]  # a function or a class
            if parameter.name not in {"self", "cls"}
        ]
        assert {*parameters[:positional], *named} == set(parameters), name  # the first by position, the rest by name
