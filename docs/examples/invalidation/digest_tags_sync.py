# ruff: noqa: S106 - as the page shows it: a secret inline
# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend(), key_secret="a secret of sixteen bytes or more")


@cache(ttl=300, key="user:{email:hmac}", tags=["user:{email:hmac}"])  # stored filled in and hashed
def get_user(email: str) -> dict[str, str]:
    return {"email": email}


def on_user_changed(email: str) -> None:
    cache.invalidate_tags(cache.key_for("user:{email:hmac}", email=email))  # the tag as it is stored


# --8<-- [end:show]
def main() -> None:
    get_user("ada@example.com")
    on_user_changed("ada@example.com")
