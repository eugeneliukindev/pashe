"""Digests in the templates of keys and tags: {name:blake2b}, {name:sha256} and {name:hmac}."""

from __future__ import annotations

import datetime as dt
import enum
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.errors import InvalidOptionsError
from tests.harness.helpers import RecordingHook, call

if TYPE_CHECKING:
    from pashe.hooks import Outcome
    from tests.harness.helpers import NewCache, Side

_SECRET = "a secret of sixteen bytes or more"
_DIGEST_HEX = 32  # 128 bits


class _Color(enum.Enum):
    RED = "red"


@dataclass
class _Filters:
    colors: set[str]
    since: dt.date


def _keys(cache_outcomes: list[Outcome]) -> list[str]:
    return [outcome.key for outcome in cache_outcomes]


async def test_equal_values_give_equal_digests(side: Side, new_process_cache: NewCache) -> None:
    outcomes: list[Outcome] = []
    cache = new_process_cache(hooks=[RecordingHook(outcomes=outcomes)])
    loads: list[object] = []

    def search(filters: dict[str, object]) -> int:
        loads.append(filters)
        return len(loads)

    cached = cache(ttl=60, key="search:{filters:blake2b}")(side.function(search))
    assert await call(cached, {"color": "red", "size": 3}) == 1
    assert await call(cached, {"size": 3, "color": "red"}) == 1
    assert await call(cached, {"size": 4, "color": "red"}) == 2
    prefix, digest = outcomes[0].key.split(":")
    assert prefix == "search"
    assert len(digest) == _DIGEST_HEX
    assert int(digest, 16) >= 0


def test_the_digests_differ_and_have_one_length() -> None:
    cache = Cache(MemoryBackend(), key_secret=_SECRET)
    digests = {spec: cache.key_for(f"{{0:{spec}}}", "ada@example.com") for spec in ("blake2b", "sha256", "hmac")}
    assert len(set(digests.values())) == len(digests)
    assert all(len(digest) == _DIGEST_HEX for digest in digests.values())
    other = Cache(MemoryBackend(), key_secret="another secret of sixteen bytes")
    assert other.key_for("{0:hmac}", "ada@example.com") != digests["hmac"]  # a new secret, new keys
    assert other.key_for("{0:blake2b}", "ada@example.com") == digests["blake2b"]  # a plain digest needs none


def test_a_template_is_checked_when_decorated() -> None:
    cache = Cache(MemoryBackend())

    def get_user(email: str) -> str:
        return email

    with pytest.raises(InvalidOptionsError, match="key_secret"):
        cache(ttl=60, key="user:{email:hmac}")(get_user)
    with pytest.raises(InvalidOptionsError, match="hsah"):
        cache(ttl=60, key="user:{email:hsah}")(get_user)
    with pytest.raises(InvalidOptionsError, match="hsah"):
        cache(ttl=60, tags=["user:{email:hsah}"])(get_user)
    with pytest.raises(InvalidOptionsError, match="hsah"):
        cache.batch(ttl=60, key="user:{:hsah}")(lambda _: {})
    with pytest.raises(InvalidOptionsError, match="16 bytes"):
        Cache(MemoryBackend(), key_secret="short")


def test_a_template_names_only_parameters() -> None:
    cache = Cache(MemoryBackend())

    def get_user(user: dict[str, int], email: str) -> str:
        return f"{user['id']}:{email}"

    with pytest.raises(InvalidOptionsError, match="usr_id"):
        cache(ttl=60, key="user:{usr_id}")(get_user)
    with pytest.raises(InvalidOptionsError, match="usr_id"):
        cache(ttl=60, key="user:{email}", tags=["user:{usr_id}"])(get_user)
    with pytest.raises(InvalidOptionsError, match=r"\{0\}"):
        cache(ttl=60, key="user:{0}")(get_user)
    with pytest.raises(InvalidOptionsError, match="usr_id"):
        cache.locked(ttl=30, key="user:{usr_id}")(get_user)
    cached = cache(ttl=60, key="user:{user[id]}:{email:blake2b}", tags=["user:{user[id]}"])(get_user)
    assert cached({"id": 1}, "ada@example.com") == "1:ada@example.com"


def test_format_specs_of_str_format_stay() -> None:
    cache = Cache(MemoryBackend())
    assert cache.key_for("price:{0:.2f}:{1:x}:{2:>4}", 1.5, 255, "a") == "price:1.50:ff:   a"


async def test_a_hashed_tag_is_made_by_cache_key(side: Side, new_process_cache: NewCache) -> None:
    cache = new_process_cache(key_secret=_SECRET)
    loads: list[str] = []

    def get_user(email: str) -> int:
        loads.append(email)
        return len(loads)

    cached = cache(ttl=60, key="user:{email:hmac}", tags=["user:{email:hmac}"])(side.function(get_user))
    assert await call(cached, "ada@example.com") == 1
    await call(cache.invalidate_tags, cache.key_for("user:{email:hmac}", email="ada@example.com"))
    assert await call(cached, "ada@example.com") == 2
    assert await call(cached.invalidate, "ada@example.com")


def test_a_batch_hashes_its_items() -> None:
    outcomes: list[Outcome] = []
    cache = Cache(MemoryBackend(), hooks=[RecordingHook(outcomes=outcomes)])

    @cache.batch(ttl=60, key="query:{:blake2b}")
    def run(queries: list[str]) -> dict[str, int]:
        return {query: len(query) for query in queries}

    assert run(["coffee", "tea"]) == {"coffee": 6, "tea": 3}
    assert all(len(key.removeprefix("query:")) == _DIGEST_HEX for key in _keys(outcomes))


def test_the_canonical_form_of_standard_types() -> None:
    cache = Cache(MemoryBackend())
    some = _Filters(colors={"red", "blue"}, since=dt.date(2026, 11, 22))
    same = _Filters(colors={"blue", "red"}, since=dt.date(2026, 11, 22))
    assert cache.key_for("{0:blake2b}", some) == cache.key_for("{0:blake2b}", same)
    assert cache.key_for("{0:blake2b}", _Color.RED) == cache.key_for("{0:blake2b}", "red")
    assert cache.key_for("{0:blake2b}", uuid.UUID(int=1)) == cache.key_for("{0:blake2b}", str(uuid.UUID(int=1)))
    with pytest.raises(TypeError, match="no canonical form"):
        cache.key_for("{0:blake2b}", object())


def test_the_default_key_suggests_a_digest() -> None:
    cache = Cache(MemoryBackend())

    @cache(ttl=60)
    def search(filters: dict[str, int]) -> int:
        return len(filters)

    with pytest.raises(TypeError, match=r"\{filters:blake2b\}"):
        search({"size": 3})


@dataclass
class _Team:
    name: str
    members: list[_Team] = field(default_factory=list)


def test_a_digest_refuses_a_cycle() -> None:
    cache = Cache(MemoryBackend())
    team = _Team("core", [_Team("infra")])
    assert cache.key_for("{0:blake2b}", team) == cache.key_for(
        "{0:blake2b}", {"name": "core", "members": [{"name": "infra", "members": []}]}
    )
    team.members.append(team)  # as a relationship of an ORM model points back
    with pytest.raises(TypeError, match="Circular"):
        cache.key_for("{0:blake2b}", team)


def test_a_plain_field_takes_only_stable_text() -> None:
    cache = Cache(MemoryBackend())
    day = dt.date(2026, 11, 22)
    assert cache.key_for("{0}:{1}:{2}:{3}", day, uuid.UUID(int=1), Decimal("1.50"), _Color.RED) == (
        "2026-11-22:00000000-0000-0000-0000-000000000001:1.50:_Color.RED"
    )
    for value in (object(), {"size": 3}, {"red"}, _Filters(colors=set(), since=day)):
        with pytest.raises(TypeError, match=r"\{user:blake2b\}"):
            cache.key_for("search:{0}", value)


def test_the_default_key_takes_dates_and_ids() -> None:
    outcomes: list[Outcome] = []
    cache = Cache(MemoryBackend(), hooks=[RecordingHook(outcomes=outcomes)])

    @cache(ttl=60)
    def report(day: dt.date, owner: uuid.UUID) -> str:
        return f"{owner.int}:{day.day}"

    assert report(dt.date(2026, 11, 22), uuid.UUID(int=1)) == "1:22"
    assert outcomes[0].key.endswith(":datetime.date(2026, 11, 22):UUID('00000000-0000-0000-0000-000000000001')")


@pytest.mark.parametrize(
    ("template", "args", "kwargs"),
    [
        ("user:{}:{}", (1, "a"), {}),
        ("pair:{1}:{0}", (1, 2), {}),
        ("user:{user_id!r}", (), {"user_id": "ada"}),
        ("padded:{n:>4}", (), {"n": 7}),
        ("nested:{0:{1}}", (7, ">3"), {}),
        ("{{literal}}:{team.name}", (), {"team": _Team("core")}),
    ],
)
def test_a_template_fills_as_str_format_does(
    template: str, args: tuple[object, ...], kwargs: dict[str, object]
) -> None:
    cache = Cache(MemoryBackend())

    filled = cache.key_for(template, *args, **kwargs)

    assert filled == template.format(*args, **kwargs)


def test_a_template_that_mixes_numbered_and_bare_fields_is_refused_as_str_format_does() -> None:
    cache = Cache(MemoryBackend())

    with pytest.raises(ValueError, match="numbering"):
        cache.key_for("{}:{0}", 1)
