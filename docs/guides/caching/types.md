# Types

A cached function is typed as the function it caches: a type checker sees the same parameters
and the same result, and a stored result comes back as that result, not as the `dict` it was
encoded into.

=== "Sync"

    ```python
    --8<-- "caching_functions/types_sync.py:show"
    --8<-- "caching_functions/types_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/types_async.py:show"
    --8<-- "caching_functions/types_async.py:calls"
    ```

## What a type checker sees

| You write | It is typed as |
| --- | --- |
| `@cache(...)` over `def get_user(user_id: int) -> User` | `CachedFunction[[int], User]`: `get_user(1)` takes what the function takes and returns a `User` |
| the same over `async def` | `AsyncCachedFunction[[int], User]`: `await get_user(1)` returns a `User` |
| a cached method | bound to its instance as a method is, without `self` |
| `get_user.get(1)` | `User | None`: `None` on a miss |
| `get_user.set(user, 1)` | takes a `User` first, then the arguments of the function |
| `@cache.batch(...)` over `def get_users(user_ids: list[int]) -> dict[int, User]` | `CachedBatchFunction[int, User]` |
| `@cache.value(...)` over `def session(sid: str) -> Session` | `CachedValue[[str], Session]` |

A wrong argument or a wrong use of the result is then an error of mypy, pyright or pyrefly, as
it would be without the cache. pashe ships `py.typed` and is checked with all three, mypy and
pyright in strict mode.

## What a result decodes as

The return annotation of the function says what a stored result decodes as; for a batch, the
type of the values of the `dict` it returns. The codec does the work, so the codec decides which
types come back whole:

| Codec | A result comes back as |
| --- | --- |
| `JsonCodec`, the default; `OrjsonCodec` | what JSON holds: `dict`, `list`, `str`, numbers, `bool`, `None`; a `TypedDict`, which is a `dict` |
| `MsgspecJsonCodec`, `MsgspecMsgpackCodec` | your dataclasses, `TypedDict`s, `msgspec.Struct`s, enums, dates, UUIDs and more |
| `PydanticCodec` | pydantic models, and what a `TypeAdapter` validates |
| `PickleCodec` | any object pickle holds |

A type the codec would give back as another one is refused when the function is decorated, not
when its first result is read: a dataclass under `JsonCodec` raises `InvalidOptionsError`, which
names the codecs that rebuild it. A function without a return annotation gets back what the
codec reads on its own.

## After the type changes

An entry remembers the shape of its type: its classes, their fields and the types of those. A
deploy that adds a field or renames a class makes the old entries misses, so a process never
decodes an entry into the wrong form; during a rolling deploy the old and the new processes each
take the entries of the other for misses and load. See [Core concepts](../../concepts.md#types) and [Codecs](../values/codecs.md).

---

API reference: [`pashe`](../../reference/caches.md), [`pashe.codecs`](../../reference/codecs.md).
