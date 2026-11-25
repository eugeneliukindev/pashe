# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache.value(ttl=600, key="otp:{email}", tags=["user:{user_id}"])
def login_code(email: str, user_id: int) -> str:
    raise NotImplementedError  # never runs: the signature finds the value, the annotation types it


def send_code(email: str, user_id: int) -> None:
    login_code.set("482913", email, user_id)  # one process sends the mail


def check_code(email: str, user_id: int, entered: str) -> bool:
    code = login_code.get(email, user_id)  # another process checks: None once it expired
    if code != entered:
        return False
    login_code.invalidate(email, user_id)  # a one-time code
    return True


# --8<-- [end:show]
