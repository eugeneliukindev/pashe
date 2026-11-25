# Invalidating on writes

`cache.invalidates(tags=...)` invalidates tags after every call of a function that writes. Its
templates are filled from the arguments of the call, as those of `tags=`, so a write of user 1
drops the results of user 1 alone.

=== "Sync"

    ```python
    --8<-- "caching_functions/invalidates_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/invalidates_async.py:show"
    ```

The tags are invalidated after a call that raised too: a write that raised may have changed the
data all the same, as a commit whose answer was lost, and a needless miss costs less than a stale
result. The error goes on to the caller. A backend that fails to invalidate goes to `on_error`
with the operation `invalidate`, and the call returns as it would without the decorator; its
results stay until their TTL. A template that names no parameter of the function is refused when
it is decorated.

## Writes in a transaction

Invalidate after the commit, not before it. A read between the invalidation and the commit misses,
loads the old row, as the write is not committed yet, and stores it under the new generation of the
tag: the old data then answers until its TTL. A read that loads before the invalidation stores
under the old generation, which the invalidation turns into a miss, so after the commit nothing
more is needed.

=== "Sync"

    ```python
    --8<-- "shop/data_changes_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "shop/data_changes_async.py:show"
    ```

`@cache.invalidates` invalidates when the function returns, so it fits a function whose
transaction ends inside it: put it above `@transaction.atomic` of Django, or on a function that
calls `session.commit()` of SQLAlchemy. A write inside a transaction that a caller commits
invalidates after that commit itself:

- Django: `transaction.on_commit(functools.partial(cache.invalidate_tags, f"user:{user_id}"))`
  runs after the commit of the outermost `atomic`, and not at all after a rollback;
- SQLAlchemy: `cache.invalidate_tags(...)` after `session.commit()`, or after the
  `with session.begin():` block.

---

API reference: [`pashe`](../../reference/caches.md).
