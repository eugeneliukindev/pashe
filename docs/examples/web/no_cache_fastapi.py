# --8<-- [start:show]
from collections.abc import MutableMapping
from typing import Any

from fastapi import FastAPI

from pashe import AsyncCache
from pashe.asgi import CacheHeadersMiddleware
from pashe.backends import AsyncMemoryBackend
from pashe.hooks import CacheHeadersHook

headers = CacheHeadersHook()
cache = AsyncCache(AsyncMemoryBackend(), hooks=[headers])
app = FastAPI()


def is_staff(scope: MutableMapping[str, Any]) -> bool:
    return (b"x-role", b"staff") in scope["headers"]  # as your authentication says


app.add_middleware(CacheHeadersMiddleware, hook=headers, allow_no_cache=is_staff)
loads: list[int] = []


@cache(ttl=60, key="product:{product_id}")
async def get_product(product_id: int) -> dict[str, object]:
    loads.append(product_id)  # your query to the database
    return {"id": product_id, "name": "Kettle"}


@app.get("/products/{product_id}")
async def product(product_id: int) -> dict[str, object]:
    return await get_product(product_id)


# --8<-- [end:show]
