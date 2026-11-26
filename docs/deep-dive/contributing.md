# Contributing

## Setup

```sh
just install
uv run prek install
```

The pre-commit hook runs the linters and the type checkers on every commit: unasyncd, ruff,
wemake-python-styleguide, mypy, pyright, pyrefly, import-linter, deptry, slotscheck, typos,
codespell and tombi.

## Commands

| Command | What it does |
| --- | --- |
| `just fmt` | regenerates the sync side, then formats the code |
| `just lint` | every linter, and the check that every fixture of the tests is used; each is a recipe of its own too, such as `just ruff` or `just vale` |
| `just types` | mypy, pyright and pyrefly; each is a recipe of its own too, such as `just mypy` |
| `just check` | `lint`, `types` and `deps` at once |
| `just test-fast` | the tests over memory and SQLite alone: no Docker, no coverage, one process |
| `just test` | every test, with Redis and a Redis Cluster in Docker; reports in `coverage/` |
| `just doctest` | the examples of the docstrings |
| `just test-flaky` | the tests of races and timing, 100 times each over xdist: after a change to them |
| `just test-lowest` | the tests with the lowest versions the floors of `pyproject.toml` allow, on Python 3.12 over Redis 6.2, in `.nox` |
| `just test-highest` | the tests with the newest versions the upper bounds allow, past `uv.lock`, on Python 3.15, in `.nox` |
| `just test-servers [server]` | the tests over Redis 6.2 and 7.4, Valkey 8 and 9, and Dragonfly, each with a cluster, or over one, such as `valkey-9`, in `.nox` |
| `just test-free-threaded [python]` | the tests on Python without the GIL, 3.14t or 3.15t or both, with the locked versions, in `.nox`; orjson has no build there |
| `just all` | everything CI runs: the checks, the tests and the examples of the docstrings and the docs |
| `just docs-serve` | the documentation with live reload |

`just` is where every check starts: the hooks of `prek.toml` and the jobs of CI call its recipes, so a
check runs the same everywhere. `just --list` shows them all.

`just test` writes `coverage/html/index.html`, with every line and branch the tests missed,
`coverage.xml` and `junit.xml`.

## The two sides

The sync side is generated from the async one by [unasyncd](https://github.com/provinzkraut/unasyncd):
edit `src/pashe/_internal/async_` and run `just fmt`. A new module of `async_` goes into
`[tool.unasyncd.files]` of `pyproject.toml`.

Three modules do what asyncio and threads do their own ways, so each side has its own, written
by hand: `tasks.py`, the tasks, waits and shared loads, `threads.py` on the sync side;
`locks/lock.py`, the lock of `with` blocks; `backends/redis/listeners.py`, how the Redis buses listen. Change
both when you change one.

In `async_`:

- every import is absolute and names the object, as
  `from pashe._internal.async_.backends.prefixed import AsyncPrefixedBackend`;
- a name of the async side differs from its sync twin, as the public `AsyncCache` and `Cache` do:
  `AsyncPrefixedBackend` and `PrefixedBackend`, `atry_take` and `try_take`, `AsyncSharedLoads` and `SharedLoads`.
  It is listed in `[tool.unasyncd.add_replacements]` of `pyproject.toml`, bare and by its full
  name.

## Layout

| Path | What it is |
| --- | --- |
| `pashe/*.py` | the public modules, by topic, and the ASGI and WSGI middlewares |
| `pashe/contrib` | one module per extra |
| `pashe/_internal` | everything private: the package is private, its modules need no underscore |

A module opens with what it is for, its main class or function; the helpers it needs follow.

A call takes what it works on by position, before `/`, as `Cache(backend)` or `locks.lock("job")`, and
its options by name, after `*`, as `GzipCompressor(level=9)`. The methods of a contract, such as
`Backend.get` or `Codec.encode`, take everything by position: pashe calls them so, and an
implementation names its parameters as it likes. A public call checks what it takes with `expect`;
pashe trusts what it hands itself.
Docstrings and examples are for what a user of pashe reaches: the public modules, the names of
their `__all__` and the methods of those classes. Inside `_internal` a reason the code cannot
show goes into a comment.

## Tests

The tests drive the public API and check what a user sees, not how pashe does it; each is
Arrange, Act and Assert, the three split by a blank line.

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

The tests are the package `tests`, and import their harness as `tests.harness`, which any IDE
finds from the root of the project. A test that takes the `redis_url` or `redis_cluster_url` fixture, or runs over a
store with a server, is marked `redis`, which `-m "not redis"` leaves out, as `just test-fast` does.
`pytest --redis-server valkey-9` runs the tests against another server of `servers.toml` and its
cluster, as `just test-servers` does; `redis-8` by default.

## Documentation

```sh
just docs-serve
```

A guide is a page of `docs/guides/<section>/`, in the order of the navigation of `zensical.toml`:
it builds on the pages before it, and ends with its API reference and the page after it.

An example of the docs is a file of `docs/examples/<topic>/`, a pair for the Sync and Async tabs,
and a page shows it, or a section of it, with `--8<-- "topic/name_sync.py:section"`:

```python
from pashe.options import Stale  # what the example needs but does not show: imports, a cache, types

cache = Cache(MemoryBackend())


# --8<-- [start:show]
@cache(ttl=60, stale=Stale(while_revalidate=30))
def get_prices() -> Prices: ...


# --8<-- [end:show]
```

The examples are code: ruff, mypy and pyright check them, and `just docs-check` runs each file,
so every cache is made and every decorator checks its options. A call that needs Redis goes
inside `main()`, which is type-checked and never run. A missing file or section fails the build.

## CI

Every push to `main` and every pull request runs the jobs of `.github/workflows/test.yml` at once:
the linters, the type checkers, the check of the dependencies and the examples once each, the
tests once per Python and server, and the floors and the newest versions of the dependencies on
every Python. The job "All checks passed" gathers them: it is the one a branch protection asks
for.

## Releasing

pashe reaches PyPI through a release on GitHub alone, by `.github/workflows/release.yml`:

1. Set the version and commit it: `uv version 1.2.3`.
2. Publish a release on GitHub with the tag `v1.2.3`.

The workflow refuses a tag that differs from the version, runs every check of CI, builds the sdist
and the wheel, checks them as PyPI reads them, imports the wheel in an environment of its own, and
publishes them by trusted publishing: no token is stored. PyPI trusts the workflow `release.yml`
of this repository in the environment `pypi`.
