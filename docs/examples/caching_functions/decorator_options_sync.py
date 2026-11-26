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
    while_revalidate=30,  # past its ttl a result answers at once for this long while one call reloads it
    if_error=IfError(600, on=(ConnectionError,)),  # it answers the errors of on for this long; 0, the default: off
    if_slow=IfSlow(60, after=0.5),  # it answers a load slower than after for this long; None, the default: off
)
# --8<-- [end:stale]
# --8<-- [start:stampede]
stampede = Stampede(
    revalidate_before=10,  # in the last seconds of the ttl, one call reloads in the background; 0: off
    lock_for=5,  # a miss loads under a lock in the backend, the others take its result; 0: off
    jitter=0.1,  # spreads every ttl by up to this share, so entries stored together do not expire together
    max_concurrent_loads=10,  # at most this many loads at once in this cache; 0: no limit
    single_flight=True,  # concurrent calls of a key in this cache share one load
)
# --8<-- [end:stampede]
# --8<-- [start:negative]
negative = Negative(
    on=(UserNotFoundError,),  # the errors kept as answers; (), the default: none
    ttl=30,  # how long one is kept, in seconds or a timedelta
)
# --8<-- [end:negative]
# --8<-- [start:store]
store = Store(
    when=worth_keeping,  # stores only a result it is true of; None, the default: every result
    slower_than=0,  # stores only a result whose load took this many seconds; 0, the default: every one
)
# --8<-- [end:store]


@cache(
    ttl=60,  # how long a result is fresh, or a function of the result that returns it
    key="user:{user_id}",  # a template over the arguments; None, the default: the name and the arguments
    tags=["users", "user:{user_id}"],  # templates of the tags that invalidate_tags drops it by
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
