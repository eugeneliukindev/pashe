"""What the pages of the docs leave out on the async side: a cache, a backend, the types and apps of yours."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, MutableMapping

cache = AsyncCache(AsyncMemoryBackend())
backend = AsyncMemoryBackend()
url = "redis://localhost:6379/0"
ip = "203.0.113.7"
app = FastAPI()


@dataclass
class User:
    id: int


@dataclass
class Report:
    id: int


@dataclass
class Export:
    user_id: int


@dataclass
class Result:
    id: int


async def load_user_from_the_database(user_id: int) -> User:
    return User(user_id)


async def build_report() -> None:
    pass


async def application(
    scope: MutableMapping[str, Any],
    receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
    send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
) -> None:
    del scope, receive, send
