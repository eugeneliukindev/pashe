# Tags

A tag names a group of results, so one call drops them all: the results of one user, of one team,
or every user. `tags=` of the decorator takes templates over the arguments, as `key=` does, and
`invalidate_tags` takes the tags as they are filled in.

!!! info "Where it works"

    A tag is a counter in the backend: every process of every machine over Redis, every process of
    one machine over SQLite, one process over memory. See [Where each feature works](../choosing.md#where-each-feature-works).

=== "Sync"

    ```python
    --8<-- "invalidation/tags_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "invalidation/tags_async.py:show"
    ```

An invalidation is two calls to the backend per tag, however many results it covers, and scans
no key. Every process over the same backend sees it at once.

A tag with a digest, such as `user:{email:hmac}`, is stored filled in and hashed: make it with
`cache.key_for("user:{email:hmac}", email=...)` to invalidate it, see [`key_for`](../caching/keys.md#digests-and-cachekey_for).

`get_user.invalidate(1)` drops one result by its arguments instead, see
[`@cache`](../caching/decorator.md#reading-and-writing-a-result).

---

API reference: [`Cache.invalidate_tags`](../../reference/caches.md#pashe.Cache.invalidate_tags), [`Cache.key_for`](../../reference/caches.md#pashe.Cache.key_for).
