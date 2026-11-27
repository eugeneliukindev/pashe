# ruff: noqa: ARG001 - a parameter there makes the key, as the page shows
import enum
from datetime import date
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


@cache(ttl=60)
def get_user(user_id: int) -> User:
    return User(id=user_id)  # your query to the database


get_user(1)  # shop:app.users.get_user:1
get_user(user_id=1)  # shop:app.users.get_user:1


@cache(ttl=60)
def get_page(team_id: int, lang: str = "ru") -> Page:
    return Page(id=team_id)


get_page(1)  # shop:app.users.get_page:1:'ru'
get_page(1, "en")  # shop:app.users.get_page:1:'en'


class Users:
    @cache(ttl=60)
    def get(self, user_id: int) -> User:
        return User(id=user_id)


Users().get(1)  # shop:app.users.Users.get:1


@cache(ttl=60)
def report(day: date, plan: Plan) -> Report:
    return Report(id=day.toordinal())


report(date(2026, 1, 2), Plan.FREE)  # shop:app.users.report:datetime.date(2026, 1, 2):Plan.FREE
# --8<-- [end:show]
