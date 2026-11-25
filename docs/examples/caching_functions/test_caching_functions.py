from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.harness.helpers import call, recording_calls

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.errors import InvalidOptionsError
from pashe.hooks import CacheStatus

_KEY = re.compile(r"# (shop:.+)$", re.MULTILINE)  # the key a call of the page says it has


@pytest.mark.parametrize("name", ["default_key", "template_key", "digest_keys"])
def test_every_call_has_the_key_the_page_says(name: str) -> None:
    said = _KEY.findall((Path(__file__).parent / f"{name}.py").read_text())

    example = importlib.import_module(f"examples.caching_functions.{name}")

    assert [outcome.key for outcome in example.outcomes] == said


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_store_when_keeps_only_a_done_order(side: str) -> None:
    example = importlib.import_module(f"examples.caching_functions.store_when_{side}")
    await call(example.main)

    await call(example.get_order, 1)
    await call(example.get_order, 2)

    statuses = [outcome.status for outcome in example.outcomes]
    assert statuses == [CacheStatus.MISS, CacheStatus.MISS, CacheStatus.HIT, CacheStatus.MISS]


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_a_batch_loads_only_the_items_it_misses(side: str, monkeypatch: pytest.MonkeyPatch) -> None:
    example = importlib.import_module(f"examples.caching_functions.batches_{side}")
    asked: list[tuple[object, ...]] = []
    monkeypatch.setattr(example, "load_users", recording_calls(example.load_users, asked))

    await call(example.main)

    assert asked == [([1, 2, 3],), ([4],)]


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_a_write_that_invalidates_makes_the_next_read_load(side: str) -> None:
    example = importlib.import_module(f"examples.caching_functions.invalidates_{side}")
    await call(example.get_user, 1)

    await call(example.rename_user, 1, "Ada")
    user = await call(example.get_user, 1)

    assert user == {"name": "Ada"}


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_a_one_time_code_checks_once(side: str) -> None:
    example = importlib.import_module(f"examples.caching_functions.value_{side}")
    await call(example.send_code, "ada@example.com", 1)

    first = await call(example.check_code, "ada@example.com", 1, "482913")
    second = await call(example.check_code, "ada@example.com", 1, "482913")

    assert (first, second) == (True, False)


@pytest.mark.parametrize("side", ["sync", "async"])
async def test_a_stored_result_decodes_as_the_return_annotation(side: str) -> None:
    example = importlib.import_module(f"examples.caching_functions.types_{side}")
    await call(example.get_user, 1)

    cached = await call(example.get_user, 1)

    assert cached == example.User(id=1, name="Ann")


def test_the_default_codec_refuses_a_type_it_cannot_rebuild() -> None:
    cache = Cache(MemoryBackend())

    def get_user(user_id: int) -> _User:
        return _User(id=user_id)

    with pytest.raises(InvalidOptionsError, match="reads _User back as another type"):
        cache(ttl=60)(get_user)


@dataclass
class _User:
    id: int
