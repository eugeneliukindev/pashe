<p align="center">
  <img src="https://raw.githubusercontent.com/eugeneliukindev/pashe/main/docs/images/logo.svg" alt="pashe" width="160">
</p>

<h1 align="center">pashe</h1>

<p align="center"><b>Caching for Python services that run as many processes.</b></p>

<p align="center">
  <a href="https://github.com/eugeneliukindev/pashe/actions/workflows/test.yml"><img src="https://github.com/eugeneliukindev/pashe/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://eugeneliukindev.github.io/pashe/"><img src="https://github.com/eugeneliukindev/pashe/actions/workflows/docs.yml/badge.svg" alt="Docs"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.12%2B-2b5b84?logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://mypy-lang.org"><img src="https://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy"></a>
  <a href="https://microsoft.github.io/pyright"><img src="https://microsoft.github.io/pyright/img/pyright_badge.svg" alt="Checked with pyright"></a>
  <a href="https://docs.astral.sh/ruff"><img src="https://img.shields.io/badge/lint-ruff-2b5b84?logo=ruff&logoColor=white" alt="Lint: ruff"></a>
  <a href="https://docs.astral.sh/ruff/formatter"><img src="https://img.shields.io/badge/format-ruff%20format-2b5b84?logo=ruff&logoColor=white" alt="Format: ruff format"></a>
  <a href="https://opensource.org/license/mit"><img src="https://img.shields.io/badge/license-MIT-f7b500" alt="License: MIT"></a>
</p>

pashe caches your functions' results in Redis, SQLite or memory. Redis here also means the
servers that speak its protocol: Valkey, Dragonfly, KeyDB, Garnet and Redis Cluster. Every process
of your service shares the entries, tags, locks and rate limits.

A cold key or a failing source won't take your service down. Callers share one load, you get
stale results while the source is slow or failing, and a fallback keeps working while Redis is
down.

```sh
pip install "pashe[redis]"
```

```python
from typing import TypedDict

from redis.asyncio import Redis

from pashe import AsyncCache
from pashe.contrib.redis import AsyncRedisBackend
from pashe.options import Stale

cache = AsyncCache(AsyncRedisBackend(Redis.from_url("redis://localhost:6379/0")), prefix="users:")


class User(TypedDict):
    id: int


async def load_user_from_the_database(user_id: int) -> User:
    return User(id=user_id)  # your query to the database


@cache(ttl=300, tags=["users"], stale=Stale(while_revalidate=30))
async def get_user(user_id: int) -> User:
    return await load_user_from_the_database(user_id)


async def main() -> None:
    await get_user(1)  # loads and stores
    await get_user(1)  # answered from Redis
    await cache.invalidate_tags("users")  # every entry tagged "users" is a miss now
```

For `def` code, use `Cache`: it has the same methods, without `await`.

## Why pashe

- **Sync and async, one API.** Use `Cache` for `def` code and `AsyncCache` for `async def`
  code. They have the same methods; on the async side you await them.
- **Stale results on purpose.** Stale-while-revalidate, stale-if-error and stale-if-slow return
  an old result while the source reloads, fails or hangs.
- **No stampedes.** Concurrent calls for one key share one load in a process, and a lock shares
  it across processes.
- **Tags without scans.** Invalidating a tag costs two backend calls, however many entries it
  covers.
- **Near caches.** A small cache in process memory sits in front of Redis. Pub/sub or Redis
  client tracking keeps it coherent.
- **Locks, rate limits, web.** You get distributed locks, sliding and fixed window limits, and
  HTTP caching headers for ASGI, WSGI and FastAPI.
- **Typed to the end.** A cached function keeps your function's signature, and its result decodes
  as its return annotation. pashe ships `py.typed`, and mypy, pyright and pyrefly check it in
  strict mode.
- **Tested against real servers.** Every scenario runs over memory, SQLite, Redis, Valkey,
  Dragonfly and a Redis Cluster, sync and async. Every docs example runs too.

## Documentation

At [eugeneliukindev.github.io/pashe](https://eugeneliukindev.github.io/pashe/) you'll find
getting started, [what to choose](https://eugeneliukindev.github.io/pashe/guides/choosing/),
guides for every feature, [how pashe compares](https://eugeneliukindev.github.io/pashe/deep-dive/comparison/)
with other caching libraries, and the API reference.

## License

MIT.
