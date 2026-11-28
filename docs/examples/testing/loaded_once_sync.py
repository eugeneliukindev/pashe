# --8<-- [start:show]
from pashe import Cache, CachedFunction
from pashe.backends import MemoryBackend

loads: list[int] = []


def make_get_user(cache: Cache) -> CachedFunction[[int], dict[str, int]]:
    @cache(ttl=300, key="user:{user_id}")
    def get_user(user_id: int) -> dict[str, int]:
        loads.append(user_id)
        return {"id": user_id}

    return get_user


def test_a_user_is_loaded_once() -> None:
    get_user = make_get_user(Cache(MemoryBackend()))
    get_user(1)
    get_user(1)
    assert loads == [1]


# --8<-- [end:show]
