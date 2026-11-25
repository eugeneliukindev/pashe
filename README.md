<p align="center">
  <img src="https://raw.githubusercontent.com/eugeneliukindev/pashe/main/docs/images/logo.svg" alt="pashe" width="160">
</p>

<h1 align="center">pashe</h1>

<p align="center"><b>Caching for Python services that run as many processes.</b></p>

<p align="center">
  <a href="https://github.com/eugeneliukindev/pashe/actions/workflows/test.yml"><img src="https://github.com/eugeneliukindev/pashe/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://eugeneliukindev.github.io/pashe/"><img src="https://github.com/eugeneliukindev/pashe/actions/workflows/docs.yml/badge.svg" alt="Docs"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.12%2B-2b5b84?logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://mypy-lang.org"><img src="https://img.shields.io/badge/typed-mypy%20strict-2b5b84" alt="Typed: mypy strict"></a>
  <a href="https://opensource.org/license/mit"><img src="https://img.shields.io/badge/license-MIT-f7b500" alt="License: MIT"></a>
</p>

pashe caches the results of your functions in Redis, SQLite or memory. Every process of a
service shares the entries, the tags, the locks and the rate limits, and a cold key or a failing
source does not take the service down: callers share one load, stale results answer while the
source is slow or failing, and a fallback keeps working while Redis is down.

```sh
uv add "pashe[redis]"
```

```python
from typing import TypedDict

from redis import Redis

from pashe import Cache
from pashe.contrib.redis import RedisBackend
from pashe.options import Stale

cache = Cache(RedisBackend(Redis.from_url("redis://localhost:6379/0")), prefix="users:")


class User(TypedDict):
    id: int


def load_user_from_the_database(user_id: int) -> User:
    return User(id=user_id)  # your query to the database


@cache(ttl=300, tags=["users"], stale=Stale(while_revalidate=30))
def get_user(user_id: int) -> User:
    return load_user_from_the_database(user_id)


get_user(1)  # loads and stores
get_user(1)  # answered from Redis
cache.invalidate_tags("users")  # every entry tagged "users" is a miss now
```

`AsyncCache` is the same API for `async def` code.

## Why pashe

- **Sync and async, the same API.** `Cache` for `def` code, `AsyncCache` for `async def` code:
  the same methods, awaited.
- **Stale results on purpose.** Stale-while-revalidate, stale-if-error and stale-if-slow answer
  from an old result while the source reloads, fails or hangs.
- **No stampedes.** Concurrent calls of a key share one load in a process, and a lock shares it
  across processes.
- **Tags without scans.** Invalidating a tag costs two calls to the backend, however many
  entries it covers.
- **Near caches.** A small cache in process memory in front of Redis, kept coherent by pub/sub
  or by Redis client tracking.
- **Locks, rate limits, web.** Distributed locks, sliding and fixed window limits, and HTTP
  caching headers for ASGI, WSGI and FastAPI.
- **Typed to the end.** A cached function keeps the signature of yours, and its result decodes
  as its return annotation. pashe ships `py.typed` and passes mypy in strict mode with extra
  checks, pyright in strict mode, pyrefly, ruff with every rule and wemake-python-styleguide.
- **Tested against real servers.** Every scenario runs on both sides over memory, SQLite, Redis
  and a Redis Cluster, and on Valkey and Dragonfly in CI; every example of the docs is a test.

## Documentation

[eugeneliukindev.github.io/pashe](https://eugeneliukindev.github.io/pashe/): getting started,
[what to choose](https://eugeneliukindev.github.io/pashe/guides/choosing/), guides for every
feature, [how pashe compares](https://eugeneliukindev.github.io/pashe/deep-dive/comparison/) with
other caching libraries, and the API reference.

## License

MIT.
