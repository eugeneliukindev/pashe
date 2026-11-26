# --8<-- [start:show]
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.options import IfError, IfSlow, Negative, Stale, Stampede, Store

cache = Cache(MemoryBackend())


class User(TypedDict):
    id: int
    active: bool


class UserNotFoundError(Exception): ...


def worth_keeping(user: User) -> bool:
    return user["active"]


# --8<-- [start:stale]
stale = Stale(
    while_revalidate=30,  # answer at once, reload behind
    if_error=IfError(600, on=(ConnectionError,)),  # answer the errors of on
    if_slow=IfSlow(60, after=0.5),  # answer a load slower than after
)
# --8<-- [end:stale]
# --8<-- [start:stampede]
stampede = Stampede(
    revalidate_before=10,  # reload before the ttl ends
    lock_for=5,  # one load in every process
    jitter=0.1,  # spread every ttl by +-10%
    max_loads=10,  # loads at once in this process
    share_loads=True,  # one load per key in this process
)
# --8<-- [end:stampede]
# --8<-- [start:negative]
negative = Negative(
    on=(UserNotFoundError,),  # errors that mean not found
    ttl=30,  # how long one is kept
)
# --8<-- [end:negative]
# --8<-- [start:store]
store = Store(
    when=worth_keeping,  # store only what it is true of
    slower_than=0,  # store only loads this slow
)
# --8<-- [end:store]


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
