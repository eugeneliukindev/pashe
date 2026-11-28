# Recommended setup

Here's what to install and configure for the common cases. The numbers behind these choices are
on the [codecs](codecs.md#how-they-compare) and [compressors](compressors.md#how-they-compare)
pages.

## In short

=== "Python services only"

    ```sh
    uv add "pashe[redis,msgspec,zstd]"
    ```

    === "Sync"

        ```python
        --8<-- "recommended_setup/msgpack_sync.py"
        ```

    === "Async"

        ```python
        --8<-- "recommended_setup/msgpack_async.py"
        ```

=== "Values read by other services"

    ```sh
    uv add "pashe[redis,msgspec]"
    ```

    === "Sync"

        ```python
        --8<-- "recommended_setup/json_sync.py"
        ```

    === "Async"

        ```python
        --8<-- "recommended_setup/json_async.py"
        ```

=== "pydantic models"

    ```sh
    uv add "pashe[redis,pydantic]"
    ```

    === "Sync"

        ```python
        --8<-- "recommended_setup/pydantic_sync.py"
        ```

    === "Async"

        ```python
        --8<-- "recommended_setup/pydantic_async.py"
        ```

| Extra | Take it when | Recommendation |
| --- | --- | --- |
| `redis` | more than one process serves the same data | :material-star:{ .recommended } production backend; Valkey works too |
| `msgspec` | your functions return dataclasses, `TypedDict`s or `msgspec.Struct`s | :material-star:{ .recommended } the default codec of a typed codebase |
| `zstd` | cached values are kilobytes, such as lists and pages | :material-star:{ .recommended } built into Python 3.14; a backport for earlier versions |
| `pydantic` | your functions return pydantic models | only for those: it's the slowest codec that rebuilds types |
| `orjson` | your functions return plain `dict`s and `list`s | the fastest for them, but it doesn't rebuild types |
| `fastapi` | you serve FastAPI | rate limits of routes and their HTTP errors |

## Backends and buses

Which backend, near cache and bus should you take? That and every other choice is on
[What to choose](choosing.md).

---
