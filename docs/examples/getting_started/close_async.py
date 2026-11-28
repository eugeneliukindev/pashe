from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend


async def main() -> None:
    async with AsyncCache(AsyncMemoryBackend()) as script_cache:  # closed when the block ends, also when it raises
        await script_cache.ping()


cache = AsyncCache(AsyncMemoryBackend())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        await cache.aclose()  # the application stops: the backend and the fallback close with the cache


app = FastAPI(lifespan=lifespan)
