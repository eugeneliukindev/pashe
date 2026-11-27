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
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-2b5b84?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff)
[![Format: ruff format](https://img.shields.io/badge/format-ruff%20format-2b5b84?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/formatter)
[![License: MIT](https://img.shields.io/badge/license-MIT-f7b500)](https://opensource.org/license/mit)

```sh
pip install "pashe[redis]"
```

[Get started](getting-started.md){ .md-button .md-button--primary }

</div>

pashe caches the results of your functions in Redis, SQLite or memory. Redis here also means the
[servers that speak its protocol](guides/backends/index.md#supported-servers): Valkey,
Dragonfly, KeyDB, Garnet and Redis Cluster. Every process of your service sees the same entries,
tags, locks and rate limits.

A cold key or a failing source won't take your service down. Callers share one load, a stale
result is returned while the source is slow or failing, and a fallback keeps working while Redis
is down.

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

    Use `Cache` for `def` code and `AsyncCache` for `async def` code. The methods are the same;
    on the async side you await them.

-   :material-history:{ .lg .middle } **Stale results on purpose**

    ---

    Stale-while-revalidate, stale-if-error and stale-if-slow return an old result while the
    source reloads, fails or hangs.

-   :material-account-group:{ .lg .middle } **No stampedes**

    ---

    Calls that miss the same key at once share one load in a process. A lock shares it across
    processes.

-   :material-tag-multiple:{ .lg .middle } **Tags without scans**

    ---

    Invalidating a tag costs two calls to the backend, no matter how many entries it covers.

-   :material-memory:{ .lg .middle } **Near caches**

    ---

    A small cache in process memory sits in front of Redis. Pub/sub or Redis client tracking
    keeps it in sync.

-   :material-lock:{ .lg .middle } **Locks, rate limits, web**

    ---

    You get distributed locks, sliding and fixed window limits, and HTTP caching headers for
    ASGI, WSGI and FastAPI.

-   :material-shield-check:{ .lg .middle } **Typed to the end**

    ---

    A cached function keeps your function's signature, and its result decodes as your return
    annotation says. pashe ships `py.typed` and passes mypy, pyright and pyrefly in strict
    mode.

-   :material-test-tube:{ .lg .middle } **Tested against real servers**

    ---

    Every scenario runs over memory, SQLite, Redis, Valkey, Dragonfly and a Redis Cluster, sync
    and async. Every example in these docs runs as a test.

</div>

## LLMs support

Do you write code with an AI assistant? Give it these files as context:

- [`llms.txt`](llms.txt): an index with a link to every page;
- [`llms-full.txt`](llms-full.txt): the complete docs in one file;
- every page as Markdown: press **Copy as Markdown** next to its title.
