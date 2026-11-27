# ruff: noqa: ARG001 - a parameter there makes the key, as the page shows
import enum
from typing import TypedDict

from pashe import Cache
from pashe.backends import MemoryBackend

__name__ = "app.users"  # the module of the page, so the keys read as it says


class User(TypedDict):
    id: int


class Page(TypedDict):
    id: int


class Report(TypedDict):
    id: int


class Price(TypedDict):
    cents: int


class Plan(enum.Enum):
    FREE = "free"


# --8<-- [start:show]
cache = Cache(MemoryBackend(), prefix="shop:")  # every key starts with the prefix


@cache(ttl=60, key="user:{user_id}")
def get_user(user_id: int) -> User:
    return User(id=user_id)  # your query to the database


get_user(1)  # shop:user:1


@cache(ttl=60, key="page:{team_id}:{lang}")
def get_page(team_id: int, lang: str = "ru") -> Page:
    return Page(id=team_id)


get_page(1)  # shop:page:1:ru


class Teams:
    team_id = 7

    @cache(ttl=60, key="team:{self.team_id}:user:{user_id}")
    def get(self, user_id: int) -> User:
        return User(id=user_id)


Teams().get(1)  # shop:team:7:user:1


@cache(ttl=60, key="price:{amount:.2f}:{user[id]}")
def price(amount: float, user: dict[str, int]) -> Price:
    return Price(cents=round(amount * 100))


price(9.9, {"id": 7})  # shop:price:9.90:7
# --8<-- [end:show]
