# Tags and invalidation

When a user changes their profile, you want to drop every cached result about that user, not
hunt down each key. A tag names a group of results, so one call drops them all: everything about
one user, one team, or every user.

!!! info "Where it works"

    A tag is a counter in the backend. Over Redis it covers every process on every machine. Over
    SQLite it covers every process on one machine, and over memory one process. See
    [Where each feature works](choosing.md#where-each-feature-works).

## Tagging a result

Give the decorator [`tags`][pashe.Cache.__call__(tags)]: templates over the arguments, the same
way `key=` works. Then call [`cache.invalidate_tags`][pashe.Cache.invalidate_tags] with the tags
filled in.

=== "Sync"

    ```python hl_lines="7 16-18"
    --8<-- "invalidation/tags_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="7 16-18"
    --8<-- "invalidation/tags_async.py:show"
    ```

Want to drop a single result? `get_user.invalidate(1)` drops it by its arguments: see
[`@cache`](caching/decorator.md#reading-and-writing-a-result).

## Tags of a batch

A batch takes [`tags`][pashe.Cache.batch(tags)] too: templates over its item, such as
`["user:{}"]`. One tag then drops both the result of `get_user(3)` and item 3 of
`get_users([...])`.

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

A tag with a digest, such as `user:{email:hmac}`, is stored filled in and hashed. To invalidate
it, build the same tag with
[`cache.key_for`][pashe.Cache.key_for]`("user:{email:hmac}", email=...)`. The `hmac` digest needs
the cache's `key_secret`.

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

Put [`cache.invalidates(tags=...)`][pashe.Cache.invalidates] on a function that writes, and it
invalidates the tags after every call. The templates are filled from the call's arguments, the same
way as `tags=`. So writing user 1 drops only the results for user 1.

=== "Sync"

    ```python hl_lines="13"
    --8<-- "caching_functions/invalidates_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="13"
    --8<-- "caching_functions/invalidates_async.py:show"
    ```

The tags are invalidated even when the call raised. Why? A write that raised may still have
changed the data, like a commit whose answer got lost. If the backend fails to invalidate, the
error goes to `on_error`, and the results stay until their TTL ends.

### Writes in a transaction

Invalidate after the commit, not before it. Otherwise a read between the invalidation and the
commit loads the old row, since the write isn't committed yet, and stores it again. Then callers
get the old data until its TTL ends.

=== "Sync"

    ```python hl_lines="9 11"
    --8<-- "shop/data_changes_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="9 11"
    --8<-- "shop/data_changes_async.py:show"
    ```

`@cache.invalidates` invalidates when the function returns. That fits a function whose
transaction ends inside it: put it above Django's `@transaction.atomic`, or on a function that
calls SQLAlchemy's `session.commit()`. If a caller commits the transaction instead, invalidate
after that commit yourself:

- Django: `transaction.on_commit(functools.partial(cache.invalidate_tags, f"user:{user_id}"))`
  runs after the commit of the outermost `atomic`, and not at all after a rollback;
- SQLAlchemy: `cache.invalidate_tags(...)` after `session.commit()`, or after the
  `with session.begin():` block.
