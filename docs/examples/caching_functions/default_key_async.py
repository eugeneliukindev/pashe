# ruff: noqa: ARG001 - a parameter there makes the key, as the page shows
import enum
from datetime import date
from typing import TypedDict

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

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
cache = AsyncCache(AsyncMemoryBackend(), prefix="shop:")  # every key starts with the prefix


@cache(ttl=60)
async def get_user(user_id: int) -> User:
    return User(id=user_id)  # your query to the database


@cache(ttl=60)
async def get_page(team_id: int, lang: str = "ru") -> Page:
    return Page(id=team_id)


class Users:
    @cache(ttl=60)
    async def get(self, user_id: int) -> User:
        return User(id=user_id)


@cache(ttl=60)
async def report(day: date, plan: Plan) -> Report:
    return Report(id=day.toordinal())


async def main() -> None:
    await get_user(1)  # shop:app.users.get_user:1
    await get_user(user_id=1)  # shop:app.users.get_user:1
    await get_page(1)  # shop:app.users.get_page:1:'ru'
    await get_page(1, "en")  # shop:app.users.get_page:1:'en'
    await Users().get(1)  # shop:app.users.Users.get:1
    await report(date(2026, 1, 2), Plan.FREE)  # shop:app.users.report:datetime.date(2026, 1, 2):Plan.FREE


# --8<-- [end:show]
