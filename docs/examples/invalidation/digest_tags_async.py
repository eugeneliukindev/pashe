# ruff: noqa: S106 - as the page shows it: a secret inline
# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend(), key_secret="a secret of sixteen bytes or more")


@cache(ttl=300, key="user:{email:hmac}", tags=["user:{email:hmac}"])  # stored filled in and hashed
async def get_user(email: str) -> dict[str, str]:
    return {"email": email}


async def on_user_changed(email: str) -> None:
    await cache.invalidate_tags(cache.key_for("user:{email:hmac}", email=email))  # the tag as it is stored


# --8<-- [end:show]
async def main() -> None:
    await get_user("ada@example.com")
    await on_user_changed("ada@example.com")
