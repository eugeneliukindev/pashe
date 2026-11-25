# --8<-- [start:show]
from fastapi import FastAPI
from pydantic import BaseModel

from pashe import AsyncCache
from pashe.asgi import CacheHeadersMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.pydantic import PydanticCodec
from pashe.hooks import CacheHeadersHook
from pashe.options import Stale


class Product(BaseModel):
    id: int
    name: str
    lang: str


headers = CacheHeadersHook()
cache = AsyncCache(AsyncMemoryBackend(), codec=PydanticCodec(), hooks=[headers])
app = FastAPI()
app.add_middleware(CacheHeadersMiddleware, hook=headers, cache_control="public")  # the same for every user


@app.get("/products/{product_id}")
@cache(ttl=60, key="product:{product_id}:{lang}", tags=["product:{product_id}"], stale=Stale(while_revalidate=30))
async def product(product_id: int, lang: str = "en") -> Product:
    return Product(id=product_id, name="Kettle", lang=lang)  # your query to the database


async def rename(product_id: int) -> None:
    # after the write of yours:
    await cache.invalidate_tags(f"product:{product_id}")  # every language of it loads again


# --8<-- [end:show]
