# Tags and invalidation

A tag names a group of results, so one call drops them all: the results of one user, of one team,
or every user.

!!! info "Where it works"

    A tag is a counter in the backend: every process of every machine over Redis, every process of
    one machine over SQLite, one process over memory. See [Where each feature works](choosing.md#where-each-feature-works).

## Tagging a result

[`tags`][pashe.Cache.__call__(tags)] of the decorator takes templates over the arguments, as
`key=` does, and [`cache.invalidate_tags`][pashe.Cache.invalidate_tags] takes the tags as they are
filled in.

=== "Sync"

    ```python hl_lines="7 16-18"
    --8<-- "invalidation/tags_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7 16-18"
    --8<-- "invalidation/tags_async.py:show"
    ```

`get_user.invalidate(1)` drops one result by its arguments instead, see
[`@cache`](caching/decorator.md#reading-and-writing-a-result).

## Tags of a batch

A batch takes [`tags`][pashe.Cache.batch(tags)] too, templates over its item such as `["user:{}"]`: one tag drops the result
of `get_user(3)` and of item 3 of `get_users([...])` alike.

=== "Sync"

    ```python hl_lines="12"
    --8<-- "invalidation/batch_tags_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="12"
    --8<-- "invalidation/batch_tags_async.py:show"
    ```

See [Batches](caching/batches.md).

## A tag with a digest

A tag with a digest, such as `user:{email:hmac}`, is stored filled in and hashed: make it with
[`cache.key_for`][pashe.Cache.key_for]`("user:{email:hmac}", email=...)` to invalidate it. The
`hmac` digest needs `key_secret` of the cache.

=== "Sync"

    ```python hl_lines="13"
    --8<-- "invalidation/digest_tags_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="13"
    --8<-- "invalidation/digest_tags_async.py:show"
    ```

See [`key_for`](caching/keys.md#digests-and-cachekey_for).

## Invalidating on writes

[`cache.invalidates(tags=...)`][pashe.Cache.invalidates] invalidates tags after every call of a function that writes. Its
templates are filled from the arguments of the call, as those of `tags=`, so a write of user 1
drops the results of user 1 alone.

=== "Sync"

    ```python hl_lines="13"
    --8<-- "caching_functions/invalidates_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="13"
    --8<-- "caching_functions/invalidates_async.py:show"
    ```

The tags are invalidated after a call that raised too: a write that raised may have changed the
data all the same, as a commit whose answer was lost. A backend that fails to invalidate goes to
`on_error`, and the results stay until their TTL.

### Writes in a transaction

Invalidate after the commit, not before it: a read between the invalidation and the commit loads
the old row, as the write is not committed yet, and stores it again, so the old data answers until
its TTL.

=== "Sync"

    ```python hl_lines="9 11"
    --8<-- "shop/data_changes_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="9 11"
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
