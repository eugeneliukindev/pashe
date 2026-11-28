import tempfile
from dataclasses import dataclass
from pathlib import Path

from pashe import AsyncCache, AsyncLocks, AsyncRateLimiter
from pashe.backends import AsyncSQLiteBackend
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.hooks import CacheHeadersHook

headers = CacheHeadersHook()  # for the HTTP headers of the web part
backend = AsyncSQLiteBackend(Path(tempfile.gettempdir()) / "shop.db")  # every worker of the machine
cache = AsyncCache(backend, prefix="shop:", codec=MsgspecJsonCodec(), hooks=[headers])
locks = AsyncLocks(backend, prefix="shop:")  # the locks and the limits of the shop over the same backend
limiter = AsyncRateLimiter(backend, prefix="shop:")


@dataclass
class Product:
    id: int
    name: str
    category: str
    price_cents: int
