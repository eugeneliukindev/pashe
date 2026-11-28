# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache.value(ttl=600, key="otp:{email}")
def login_code(email: str) -> str:
    raise NotImplementedError  # never runs: the signature finds the value, the annotation types it


def send_code(email: str) -> None:
    login_code.set("482913", email)  # one process sends the mail


def check_code(
    email: str,
    entered: str,
) -> bool:
    code = login_code.get(email)  # another process checks: None once it expired
    if code != entered:
        return False
    login_code.invalidate(email)  # a one-time code
    return True


# --8<-- [end:show]
