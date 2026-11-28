# ruff: noqa: ARG001 - a parameter there makes the key, as the page shows
from dataclasses import dataclass

from pashe import Cache
from pashe.backends import MemoryBackend

__name__ = "app.users"  # the module of the page, so the keys read as it says


@dataclass
class Filters:
    category: str
    colors: set[str]


# --8<-- [start:show]
cache = Cache(MemoryBackend(), prefix="shop:")  # every key starts with the prefix


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
