# ruff: noqa: ARG001 - a handler takes the request whether it reads it or not
# --8<-- [start:imports]
import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pashe.asgi import CacheHeadersMiddleware
from pashe.errors import RateLimitedError
from pashe.ratelimit import per_minute

# --8<-- [end:imports]
from examples.shop.shop_async import Product, cache, headers
from examples.shop.slow_query_async import get_product

# --8<-- [start:show]
app = FastAPI()
app.add_middleware(CacheHeadersMiddleware, hook=headers)  # ETag, Cache-Control and Cache-Status


@app.exception_handler(RateLimitedError)
async def rate_limited(request: Request, error: RateLimitedError) -> JSONResponse:
    retry_after = str(math.ceil(error.retry_after))
    headers = {"Retry-After": retry_after}
    return JSONResponse({"detail": str(error)}, status_code=429, headers=headers)


@app.get("/products/{product_id}")
async def product_page(product_id: int, request: Request) -> Product:
    client = request.client.host if request.client else "unknown"
    await cache.rate_limit(f"client:{client}", per_minute(600))
    return await get_product(product_id)


# --8<-- [end:show]
