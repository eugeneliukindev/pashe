# ruff: noqa: ARG001 - a handler takes the request whether it reads it or not
# --8<-- [start:imports]
import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pashe.asgi import CacheHeadersMiddleware
from pashe.errors import RateLimitedError
from pashe.ratelimit import SlidingWindow

# --8<-- [end:imports]
from examples.shop.shop_sync import Product, headers, limiter
from examples.shop.slow_query_sync import get_product

# --8<-- [start:show]
app = FastAPI()
app.add_middleware(CacheHeadersMiddleware, hook=headers)  # ETag, Cache-Control and Cache-Status


@app.exception_handler(RateLimitedError)
async def rate_limited(request: Request, error: RateLimitedError) -> JSONResponse:
    retry_after = str(math.ceil(error.retry_after))
    headers = {"Retry-After": retry_after}
    return JSONResponse({"detail": str(error)}, status_code=429, headers=headers)


@app.get("/products/{product_id}")
def product_page(product_id: int, request: Request) -> Product:
    client = request.client.host if request.client else "unknown"
    limiter.count(f"client:{client}", SlidingWindow.per_minute(600))
    return get_product(product_id)


# --8<-- [end:show]
