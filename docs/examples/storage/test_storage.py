from __future__ import annotations

from examples.storage import cached_result


def test_a_cached_result_keeps_the_bytes_the_page_shows() -> None:
    cached_result.get_user(1)

    raw = cached_result.backend.get("shop:user:1")

    assert raw is not None
    assert len(raw) == 49
    assert raw.endswith(b'{"id":1,"name":"Ada"}')
