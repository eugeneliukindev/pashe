# Caching a function

`@cache(...)` caches the results of a function, `def` for a `Cache` and `async def` for an
`AsyncCache`: the first call of
the arguments runs it and stores the result, the next ones are answered from the backend until its
TTL ends.

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_sync.py:show"
    ```

    1. Fresh for 5 minutes: seconds, a `timedelta`, or a function of the result.
    2. The key of a call: `user:1` for `get_user(1)`, under the `prefix` of the cache.
    3. `cache.invalidate_tags("users")` drops every result stored with this tag, without a scan.
    4. TTLs spread by +-10%, so entries stored together do not expire together.
    5. The return annotation says what the stored value decodes as.

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_async.py:show"
    ```

    1. Fresh for 5 minutes: seconds, a `timedelta`, or a function of the result.
    2. The key of a call: `user:1` for `get_user(1)`, under the `prefix` of the cache.
    3. `cache.invalidate_tags("users")` drops every result stored with this tag, without a scan.
    4. TTLs spread by +-10%, so entries stored together do not expire together.
    5. The return annotation says what the stored value decodes as.

The options of [stale results](../failures/stale.md) and of [stampedes](../failures/stampedes.md) have their own
pages.

!!! warning "Do not change a result in place"

    Concurrent calls of a key that miss together share one load, `Stampede(share_loads=True)` by
    default, and get the same object: a change one caller makes, another sees. Copy a result
    before you change it.

## Every option

=== "Sync"

    ```python
    --8<-- "caching_functions/decorator_options_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/decorator_options_async.py:show"
    ```

API reference: [`Cache.__call__`](../../reference/caches.md#pashe.Cache.__call__), [`Stale`](../../reference/options.md#pashe.options.Stale), [`IfError`](../../reference/options.md#pashe.options.IfError), [`IfSlow`](../../reference/options.md#pashe.options.IfSlow), [`Stampede`](../../reference/options.md#pashe.options.Stampede), [`Negative`](../../reference/options.md#pashe.options.Negative), [`Store`](../../reference/options.md#pashe.options.Store).

## Reading and writing a result

=== "Sync"

    ```python
    --8<-- "caching_functions/methods_sync.py:show"
    ```

=== "Async"

    ```python
    --8<-- "caching_functions/methods_async.py:show"
    ```

`get`, `set`, `refresh` and `invalidate` take the same arguments as the function, so they find the same entry.

!!! warning "Cached methods share one entry across instances"

    A method can be cached too. `self` and `cls` are left out of the default key, so every
    instance shares one entry per arguments; when the result depends on the instance, name it in
    the template, such as `key="user:{self.id}"`.

API reference: [`CachedFunction`](../../reference/caches.md#pashe.CachedFunction).

---

API reference: [`pashe`](../../reference/caches.md), [`pashe.options`](../../reference/options.md).
