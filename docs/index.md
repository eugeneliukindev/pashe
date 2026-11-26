---
social:
  cards_layout_options:
    title: Stale results, no stampedes, tags without scans
---

<div class="pashe-hero" markdown>

![](images/logo.svg){ .pashe-hero__logo width="148" height="148" }

# pashe

<p class="pashe-hero__tagline">Caching for Python services that run as many processes.</p>

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-2b5b84?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-f7b500)](https://opensource.org/license/mit)
[![Code style: wemake](https://img.shields.io/badge/style-wemake-000000.svg)](https://github.com/wemake-services/wemake-python-styleguide)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-2b5b84)](https://mypy-lang.org)

```sh
uv add "pashe[redis]"
```

[Get started](getting-started.md){ .md-button .md-button--primary }
[What to choose](guides/choosing.md){ .md-button }

</div>

pashe caches the results of your functions in Redis, SQLite or memory. Every process of a service
shares the entries, the tags, the locks and the rate limits, and a cold key or a failing source
does not take the service down: callers share one load, stale results answer while the source
is slow or failing, and a fallback keeps working while Redis is down.

=== "Sync"

    ```python
    --8<-- "index/quick_start_sync.py:imports"
    --8<-- "index/quick_start_sync.py:show"
    --8<-- "index/quick_start_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "index/quick_start_async.py:imports"
    --8<-- "index/quick_start_async.py:show"
    --8<-- "index/quick_start_async.py:calls"
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
    annotation. pashe ships `py.typed` and passes mypy in strict mode with extra checks,
    pyright in strict mode, pyrefly, ruff with every rule and wemake-python-styleguide.

-   :material-test-tube:{ .lg .middle } **Tested against real servers**

    ---

    Every scenario runs on both sides over memory, SQLite, Redis and a Redis Cluster, and on
    Valkey and Dragonfly in CI; every example of these docs is a test.

</div>

## LLMs support

Do you write code with an AI assistant? These files give it the docs as context:

- [`llms.txt`](llms.txt): an index with a link to every page;
- [`llms-full.txt`](llms-full.txt): the complete docs in one file;
- every page as Markdown: press **Copy as Markdown** next to its title.

Next: [Getting started](getting-started.md).
