"""What only the memory backend does: limits and expiry by its clock."""

from __future__ import annotations

import pytest

from pashe.backends import MemoryBackend
from pashe.errors import InvalidOptionsError, ValueTooLargeError


class _Clock:
    __slots__ = ("now",)

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_expired_entry_is_a_miss() -> None:
    clock = _Clock()
    backend = MemoryBackend(clock=clock)
    backend.set("k", b"v", ttl=10)
    clock.now = 9.5
    assert backend.ttl("k") == 0.5
    clock.now = 10
    assert backend.get("k") is None


def test_clear_removes_every_entry() -> None:
    backend = MemoryBackend()
    backend.set_many({"a": b"1", "b": b"2"})
    backend.clear()
    assert backend.get_many(["a", "b"]) == [None, None]
    backend.set("c", b"3")  # what clear freed counts again
    assert backend.get("c") == b"3"


def test_evicts_least_recently_used() -> None:
    backend = MemoryBackend(max_entries=2)
    backend.set("a", b"1")
    backend.set("b", b"2")
    backend.get("a")
    backend.set("c", b"3")
    assert backend.get_many(["a", "b", "c"]) == [b"1", None, b"3"]


def test_max_bytes() -> None:
    backend = MemoryBackend(max_bytes=4)
    backend.set("a", b"1")
    backend.set("b", b"22")
    assert backend.get_many(["a", "b"]) == [None, b"22"]
    with pytest.raises(ValueTooLargeError):
        backend.set("b", b"4444")
    assert backend.get("b") is None  # the old value must not answer after a failed write


@pytest.mark.parametrize(("max_entries", "max_bytes"), [(0, None), (1000, 0)])
def test_rejects_limits_that_are_not_positive(max_entries: int, max_bytes: int | None) -> None:
    with pytest.raises(InvalidOptionsError):
        MemoryBackend(max_entries=max_entries, max_bytes=max_bytes)


def test_a_live_lock_or_counter_is_evicted_last() -> None:
    backend = MemoryBackend(max_entries=3)
    backend.set_if_absent("lock", b"owner", ttl=10)
    backend.incr("rate", 1, ttl=10)
    for key in ("a", "b", "c"):
        backend.set(key, b"1")
    assert backend.get_many(["lock", "rate", "a", "b", "c"]) == [b"owner", b"1", None, None, b"1"]
    backend.set_if_absent("other", b"owner", ttl=10)
    backend.set_if_absent("third", b"owner", ttl=10)  # nothing else is left to evict: the oldest lock goes
    assert backend.get_many(["lock", "rate", "other", "third"]) == [None, b"1", b"owner", b"owner"]


def test_delete_many_counts_the_keys_that_existed() -> None:
    backend = MemoryBackend()
    backend.set_many({"a": b"1", "b": b"1", "c": b"1"})

    removed = backend.delete_many(["a", "b", "b", "missing"])

    assert removed == 2
    assert backend.get_many(["a", "b", "c"]) == [None, None, b"1"]
