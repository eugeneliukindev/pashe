# Contributing

## Setup

```sh
just install
uv run prek install
```

The pre-commit hook runs the linters and type checkers on every commit: unasyncd, ruff,
wemake-python-styleguide, mypy, pyright, pyrefly, import-linter, deptry, slotscheck, typos,
codespell and tombi.

## Commands

| Command | What it does |
| --- | --- |
| `just fmt` | regenerates the sync side, then formats the code |
| `just lint` | every linter, plus the check that every test fixture is used; each one is also a recipe of its own, such as `just ruff` or `just vale` |
| `just types` | mypy, pyright and pyrefly; each one is also a recipe of its own, such as `just mypy` |
| `just check` | `lint`, `types` and `deps` at once |
| `just test-fast` | the tests over memory and SQLite alone: no Docker, no coverage, one process |
| `just test` | every test, with Redis and a Redis Cluster in Docker; reports in `coverage/` |
| `just doctest` | the docstring examples |
| `just bench` | the benchmarks in `benchmarks/`: the codecs, the compressors and a cache call over each backend, with Redis in Docker |
| `just test-flaky` | the race and timing tests, 100 times each over xdist; run it after you change them |
| `just test-lowest` | the tests with the lowest versions that the floors in `pyproject.toml` allow, on Python 3.12 over Redis 6.2, in `.nox` |
| `just test-highest` | the tests with the newest versions the upper bounds allow, past `uv.lock`, on Python 3.15, in `.nox` |
| `just test-servers [server]` | the tests over Redis 6.2 and 7.4, Valkey 8 and 9, and Dragonfly, each with a cluster, or over one, such as `valkey-9`, in `.nox` |
| `just test-free-threaded [python]` | the tests on Python without the GIL, 3.14t or 3.15t or both, with the locked versions, in `.nox`; orjson has no build there |
| `just all` | everything CI runs: the checks, the tests, and the docstring and docs examples |
| `just docs-serve` | the documentation with live reload |

Every check starts from `just`. The hooks in `prek.toml` and the CI jobs call its recipes, so a
check runs the same way everywhere. `just --list` shows them all.

`just test` writes `coverage/html/index.html`, with every line and branch the tests missed. It
also writes `coverage.xml` and `junit.xml`.

## The two sides

[unasyncd](https://github.com/provinzkraut/unasyncd) generates the sync side from the async
one. Edit `src/pashe/_internal/async_` and run `just fmt`. When you add a module to `async_`, add
it to `[tool.unasyncd.files]` in `pyproject.toml`.

Three modules do things that asyncio and threads each do their own way, so each side has its own
hand-written copy:

- `tasks.py` (`threads.py` on the sync side): the tasks, waits and shared loads;
- `locks/lock.py`: the lock of `with` blocks;
- `backends/redis/listeners.py`: how the Redis buses listen.

When you change one side, change the other too.

In `async_`:

- every import is absolute and names the object, such as
  `from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend`;
- an async name differs from its sync twin, the way the public `AsyncCache` and `Cache` do:
  `AsyncPrefixedBackend` and `PrefixedBackend`, `atry_take` and `try_take`, `AsyncSharedLoads`
  and `SharedLoads`. List it in `[tool.unasyncd.add_replacements]` in `pyproject.toml`, both bare
  and by its full name.

## Layout

| Path | What it is |
| --- | --- |
| `pashe/*.py` | the public modules, by topic, and the ASGI and WSGI middlewares |
| `pashe/contrib` | one module per extra |
| `pashe/_internal` | everything private; since the package is private, its modules need no underscore |

A module opens with what it's for, its main class or function. The helpers it needs come after.

A call takes what it works on by position, before `/`, such as `Cache(backend)` or
`locks.lock("job")`. It takes its options by name, after `*`, such as `GzipCompressor(level=9)`.

The methods of a contract, such as `Backend.get` or `Codec.encode`, take everything by position.
That's how pashe calls them, so an implementation can name its parameters as it likes.

A public call checks what it takes with `expect`; pashe trusts what it passes to itself.

Docstrings and examples cover what pashe users can reach: the public modules, the names in their
`__all__` and the methods of those classes. Inside `_internal`, a reason the code can't show goes
into a comment.

## Tests

The tests drive the public API and check what a user sees, not how pashe does it. Each test is
Arrange, Act and Assert, with a blank line between the three.

| Where | What |
| --- | --- |
| `tests/test_cached.py`, `tests/test_cache_api.py` | most tests: the caches of both sides over every store of `stores.py`, through the fixture `new_process_cache`; a test of a failing or a closed backend, or of decoration alone, over memory |
| `tests/backends` | the contract every backend keeps, over every store of `stores.py` and both sides |
| `tests/test_processes.py` | the core scenarios of caches that stand for processes, over every store of `stores.py` |
| `tests/contrib`, `test_asgi.py`, `test_wsgi.py` | the web integrations, end to end |
| `tests/harness/helpers.py` | `Side`, the classes of each side, which the fixture `side` gives a test; fakes of a clock, a backend and a function, and calls of either side |
| `tests/harness/stores.py` | the stores the tests run over, memory, SQLite, Redis and the cluster: a new store is one entry there |
| `tests/harness/servers.py` | the plugin that starts a Redis and a cluster in Docker for each test process, when its first test asks for one |
| `tests/harness/servers.toml` | the servers the tests run against, by name, with the images of each and its cluster, which CI runs one by one: a new server is one table there |
| `tests/harness/cluster.sh` | the script that starts the nodes of the cluster in their container and joins them |

The tests are the package `tests`, and they import their harness as `tests.harness`, which any
IDE finds from the project root.

A test that takes the `redis_url` or `redis_cluster_url` fixture, or runs over a store with a
server, is marked `redis`. `-m "not redis"` leaves those out, as `just test-fast` does.

`pytest --redis-server valkey-9` runs the tests against another server from `servers.toml` and
its cluster, as `just test-servers` does. The default is `redis-8`.

## Documentation

```sh
just docs-serve
```

A guide is a page in `docs/guides/`, in the navigation order of `zensical.toml`. It builds on
the pages before it, and it links the API reference where it first names an object.

A docs example is a file in `docs/examples/<topic>/`, one of a pair for the Sync and Async tabs.
A page shows it, or a section of it, with `--8<-- "topic/name_sync.py:section"`:

```python
from pashe.options import Stale  # what the example needs but does not show: imports, a cache, types

cache = Cache(MemoryBackend())


# --8<-- [start:show]
@cache(ttl=60, stale=Stale(while_revalidate=30))
def get_prices() -> Prices: ...


# --8<-- [end:show]
```

The examples are code. ruff, mypy and pyright check them, and `just docs-check` runs each file,
so every cache gets created and every decorator checks its options. A call that needs Redis goes
inside `main()`, which is type-checked but never run. A missing file or section fails the build.

## CI

Every push to `main` and every pull request runs the jobs in `.github/workflows/test.yml` at
once:

- the linters, the type checkers, the dependency check and the examples, once each;
- the tests, once per Python and server;
- the lowest and the newest dependency versions, on every Python.

The job "All checks passed" gathers them all. That's the job a branch protection rule asks for.

## Releasing

pashe reaches PyPI only through a GitHub release, run by `.github/workflows/release.yml`:

1. Set the version and commit it: `uv version 1.2.3`.
2. Publish a release on GitHub with the tag `v1.2.3`.

The workflow refuses a tag that differs from the version. Then it runs every CI check, builds
the sdist and the wheel, and checks them the way PyPI reads them. It imports the wheel in an
environment of its own, and publishes both by trusted publishing, so no token is stored. PyPI
trusts this repository's `release.yml` workflow in the `pypi` environment.
