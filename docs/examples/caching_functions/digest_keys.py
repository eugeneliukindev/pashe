# ruff: noqa: ARG001 - a parameter there makes the key, as the page shows
from dataclasses import dataclass

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.hooks import Outcome

from examples.recorded import Record

__name__ = "app.users"  # the module of the page, so the keys read as it says

outcomes: list[Outcome] = []  # the key of every call, for the test
cache = Cache(MemoryBackend(), prefix="shop:", hooks=[Record(outcomes)])


@dataclass
class Filters:
    category: str
    colors: set[str]


# --8<-- [start:show]
@cache(ttl=60, key="search:{filters:blake2b}")
def search(filters: Filters) -> list[int]:
    return [1, 2, 3]  # the ids your search finds


search(Filters("coffee", {"red", "blue"}))  # shop:search:30f829b6221268747b477111a6a07725
search(Filters("coffee", {"blue", "red"}))  # shop:search:30f829b6221268747b477111a6a07725


@cache(ttl=60, key="search:{filters.category}:{filters:blake2b}")
def find(filters: Filters) -> list[int]:
    return [1, 2, 3]


find(Filters("coffee", {"red", "blue"}))  # shop:search:coffee:30f829b6221268747b477111a6a07725
# --8<-- [end:show]
