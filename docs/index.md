---
social:
  cards_layout_options:
    title: Stale results, no stampedes, tags without scans
---

<div class="pashe-hero" markdown>

![pashe](images/logo.svg){ .pashe-hero__logo width="148" height="148" }

# pashe

<p class="pashe-hero__tagline">Caching for Python services that run as many processes.</p>

[![Tests](https://github.com/eugeneliukindev/pashe/actions/workflows/test.yml/badge.svg)](https://github.com/eugeneliukindev/pashe/actions/workflows/test.yml)
[![Docs](https://github.com/eugeneliukindev/pashe/actions/workflows/docs.yml/badge.svg)](https://github.com/eugeneliukindev/pashe/actions/workflows/docs.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-2b5b84?logo=python&logoColor=white)](https://www.python.org)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-2b5b84)](https://mypy-lang.org)
[![Typed: pyright strict](https://img.shields.io/badge/typed-pyright%20strict-2b5b84)](https://microsoft.github.io/pyright)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-2b5b84)](https://docs.astral.sh/ruff)
[![Format: ruff format](https://img.shields.io/badge/format-ruff%20format-2b5b84)](https://docs.astral.sh/ruff/formatter)
[![License: MIT](https://img.shields.io/badge/license-MIT-f7b500)](https://opensource.org/license/mit)

```sh
pip install "pashe[redis]"
```

[Get started](getting-started.md){ .md-button .md-button--primary }
[What to choose](guides/choosing.md){ .md-button }

</div>

pashe caches the results of your functions in Redis, SQLite or memory. Every process of a service
shares the entries, the tags, the locks and the rate limits, and a cold key or a failing source
does not take the service down: callers share one load, stale results answer while the source
is slow or failing, and a fallback keeps working while Redis is down.

=== "Async"

    ```python
    --8<-- "index/quick_start_async.py:imports"
    --8<-- "index/quick_start_async.py:show"
    --8<-- "index/quick_start_async.py:calls"
    ```

=== "Sync"

    ```python
    --8<-- "index/quick_start_sync.py:imports"
    --8<-- "index/quick_start_sync.py:show"
    --8<-- "index/quick_start_sync.py:calls"
    ```

<div class="grid cards" markdown>

-   :material-swap-horizontal:{ .lg .middle } **Sync and async, the same API**

    ---

    `Cache` for `def` code, `AsyncCache` for `async def` code: the same methods, awaited.

-   :material-history:{ .lg .middle } **Stale results on purpose**

    ---

    Stale-while-revalidate, stale-if-error and stale-if-slow answer from an old result while
    the source reloads, fails or hangs.

-   :material-account-group:{ .lg .middle } **No stampedes**

    ---

    Concurrent calls of a key share one load in a process, and a lock shares it across
    processes.

-   :material-tag-multiple:{ .lg .middle } **Tags without scans**

    ---

    Invalidating a tag costs two calls to the backend, however many entries it covers.

-   :material-memory:{ .lg .middle } **Near caches**

    ---

    A small cache in process memory in front of Redis, kept coherent by pub/sub or by
    Redis client tracking.

-   :material-lock:{ .lg .middle } **Locks, rate limits, web**

    ---

    Distributed locks, sliding and fixed window limits, and HTTP caching headers for ASGI,
    WSGI and FastAPI.

-   :material-shield-check:{ .lg .middle } **Typed to the end**

    ---

    A cached function keeps the signature of yours, and its result decodes as its return
    annotation. pashe ships `py.typed` and is checked with mypy, pyright and pyrefly in strict
    mode.

-   :material-test-tube:{ .lg .middle } **Tested against real servers**

    ---

    Every scenario runs over memory, SQLite, Redis, Valkey, Dragonfly and a Redis Cluster, sync
    and async; every example of these docs runs.

</div>

## LLMs support

Do you write code with an AI assistant? These files give it the docs as context:

- [`llms.txt`](llms.txt): an index with a link to every page;
- [`llms-full.txt`](llms-full.txt): the complete docs in one file;
- every page as Markdown: press **Copy as Markdown** next to its title.

Next: [Getting started](getting-started.md).
