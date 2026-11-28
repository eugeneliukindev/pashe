# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache(ttl=600, tags=["users", "user:{user_id}", "team:{team_id}"])
def get_member(user_id: int, team_id: int) -> dict[str, int]:
    return {"user": user_id, "team": team_id}


def main() -> None:
    get_member(1, team_id=7)
    get_member(2, team_id=7)

    cache.invalidate_tags("user:1")  # get_member(1, ...) reloads, get_member(2, ...) does not
    cache.invalidate_tags("team:7")  # both reload
    cache.invalidate_tags("users")  # every result of every member reloads


# --8<-- [end:show]
