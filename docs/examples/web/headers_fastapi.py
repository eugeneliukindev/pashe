# --8<-- [start:show]
from fastapi import FastAPI

from pashe import AsyncCache
from pashe.asgi import CacheHeadersMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.hooks import CacheHeadersHook

headers = CacheHeadersHook()
cache = AsyncCache(AsyncMemoryBackend(), hooks=[headers])
app = FastAPI()
app.add_middleware(CacheHeadersMiddleware, hook=headers)


@cache(ttl=60, key="product:{product_id}")
async def get_product(product_id: int) -> dict[str, object]:
    return {"id": product_id, "name": "Kettle"}


@app.get("/products/{product_id}")
async def product(product_id: int) -> dict[str, object]:
    return await get_product(product_id)


# --8<-- [end:show]
