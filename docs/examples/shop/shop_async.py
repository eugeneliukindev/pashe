from dataclasses import dataclass

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec
from pashe.hooks import CacheHeadersHook

headers = CacheHeadersHook()  # for the HTTP headers of the web part
cache = AsyncCache(AsyncMemoryBackend(), prefix="shop:", codec=MsgspecJsonCodec(), hooks=[headers])


@dataclass
class Product:
    id: int
    name: str
    category: str
    price_cents: int
