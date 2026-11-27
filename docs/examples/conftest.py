from __future__ import annotations

import inspect
import sys
from typing import TYPE_CHECKING

import prometheus_client
import pytest

from pashe import AsyncCache, Cache

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture(autouse=True)
async def fresh_examples(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Make every test import the examples anew, so their caches start empty, and close what they opened."""
    monkeypatch.setenv("CACHE_SECRET", "a secret of sixteen bytes or more")  # what PickleCodec of a page reads
    for name in [name for name in sys.modules if name.startswith("examples.")]:
        monkeypatch.delitem(sys.modules, name)
    # the hook of Prometheus registers its metrics in the global registry, which a page of each side
    # fills again: the collectors a test adds go after it. The registry lists them only privately.
    registry = prometheus_client.REGISTRY
    collectors = set(registry._collector_to_names)  # noqa: SLF001

    yield

    for collector in set(registry._collector_to_names) - collectors:  # noqa: SLF001
        registry.unregister(collector)

    examples = [module for name, module in sys.modules.items() if name.startswith("examples.")]
    # by id: a page imports the cache of the stubs, so one cache is a name of several modules
    caches = {
        id(value): value
        for module in examples
        for value in vars(module).values()
        if isinstance(value, Cache | AsyncCache)
    }
    for cache in caches.values():  # a cache closes its backend, such as the file of SQLite
        if isinstance(cache, AsyncCache):
            await cache.aclose()
        else:
            cache.close()
    for module in examples:  # what a page opens apart from a cache, such as the stand-ins of the shop
        close = getattr(module, "close", None)
        if callable(close):
            closing = close()
            if inspect.isawaitable(closing):
                await closing
