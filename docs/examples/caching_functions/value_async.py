# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

cache = AsyncCache(AsyncMemoryBackend())


@cache.value(ttl=600, key="otp:{email}", tags=["user:{user_id}"])
async def login_code(email: str, user_id: int) -> str:
    raise NotImplementedError  # never runs: the signature finds the value, the annotation types it


async def send_code(email: str, user_id: int) -> None:
    await login_code.set("482913", email, user_id)  # one process sends the mail


async def check_code(email: str, user_id: int, entered: str) -> bool:
    code = await login_code.get(email, user_id)  # another process checks: None once it expired
    if code != entered:
        return False
    await login_code.invalidate(email, user_id)  # a one-time code
    return True


# --8<-- [end:show]
