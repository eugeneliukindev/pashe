import tempfile
from dataclasses import dataclass
from pathlib import Path

from pashe import Cache, Locks, RateLimiter
from pashe.backends import SQLiteBackend
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.hooks import CacheHeadersHook

headers = CacheHeadersHook()  # for the HTTP headers of the web part
backend = SQLiteBackend(Path(tempfile.gettempdir()) / "shop.db")  # every worker of the machine
cache = Cache(backend, prefix="shop:", codec=MsgspecJsonCodec(), hooks=[headers])
locks = Locks(backend, prefix="shop:")  # the locks and the limits of the shop over the same backend
limiter = RateLimiter(backend, prefix="shop:")


@dataclass
class Product:
    id: int
    name: str
    category: str
    price_cents: int
