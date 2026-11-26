from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pashe import Cache
from pashe.backends import MemoryBackend


def main() -> None:
    with Cache(MemoryBackend()) as script_cache:  # closed when the block ends, also when it raises
        script_cache.ping()


cache = Cache(MemoryBackend())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        cache.close()  # the application stops: the backend and the fallback close with the cache


app = FastAPI(lifespan=lifespan)
