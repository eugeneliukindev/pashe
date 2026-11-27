# --8<-- [start:show]
from datetime import timedelta
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import Negative, Stale, Stampede, Store

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int
    active: bool


class UserNotFoundError(Exception): ...


def worth_keeping(user: User) -> bool:
    return user["active"]


stale = Stale(
    while_revalidate=30,  # answer at once, reload behind
    if_error=timedelta(minutes=10),  # answer the errors of if_error_on
    if_error_on=(ConnectionError,),  # the errors it answers; every Exception by default
    if_slow=60,  # answer a load slower than slow_after
    slow_after=0.5,  # how long a call waits for the load
)
stampede = Stampede(
    revalidate_before=10,  # reload before the ttl ends
    lock_for=5,  # one load in every process
    jitter=0.1,  # spread every ttl by +-10%
    max_loads=10,  # loads at once in this process
    share_loads=True,  # one load per key in this process
)
negative = Negative(
    on=(UserNotFoundError,),  # errors that mean not found
    ttl=30,  # how long one is kept
)
store = Store(
    when=worth_keeping,  # store only what it is true of
    slower_than=0,  # store only loads this slow
)


@cache(
    ttl=60,  # fresh this long, or a function of the result
    key="user:{user_id}",  # a template; None: name and arguments
    tags=["users", "user:{user_id}"],  # what invalidate_tags drops it by
    stale=stale,  # when an old result answers
    stampede=stampede,  # how the loads of a key are shared
    negative=negative,  # which errors are kept as answers
    store=store,  # which results are stored
)
def get_user(user_id: int) -> User:
    return User(id=user_id, active=True)  # your query to the database


def main() -> None:
    get_user(1)


# --8<-- [end:show]
