"""What the pages of the docs leave out on the sync side: a cache, a backend, the types and apps of yours."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pashe import Cache
from pashe.backends import MemoryBackend

if TYPE_CHECKING:
    from collections.abc import Iterable
    from wsgiref.types import StartResponse, WSGIEnvironment

cache = Cache(MemoryBackend())
backend = MemoryBackend()
url = "redis://localhost:6379/0"
ip = "203.0.113.7"


@dataclass
class User:
    id: int


@dataclass
class Report:
    id: int


@dataclass
class Export:
    user_id: int


def load_user_from_the_database(user_id: int) -> User:
    return User(user_id)


def build_report() -> None:
    pass


def application(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
    del environ
    start_response("200 OK", [])
    return [b""]
