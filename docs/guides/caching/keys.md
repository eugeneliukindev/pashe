# Keys

A call's key names its entry in the backend. It's the cache's `prefix`, followed by the
function's key: either the default key, or the [`key`][pashe.Cache.__call__(key)] template filled
in with the arguments.

The keys below come from a cache with `prefix="shop:"` and functions in the file `app/users.py`,
the module `app.users`.

## The default key

Without `key=`, the key is the module and the function's qualified name, then the `repr` of each
argument, joined by `:`. Each call below shows its key:

=== "Sync"

    ```python title="app/users.py" hl_lines="4 13 23 31"
    --8<-- "caching_functions/default_key_sync.py:show"
    ```

=== "Async"

    ```python title="app/users.py" hl_lines="4 9 15 20"
    --8<-- "caching_functions/default_key_async.py:show"
    ```

- pashe binds the arguments to the signature first. So a positional call and a keyword call share
  a key, and a default value goes in the key as if you'd passed it.
- A string is quoted by its `repr`, so `get_page(1, "2")` and `get_page(1, 2)` don't share a key.
- A method's `self` and `cls` are left out, so all instances share an entry for the same
  arguments.
- An argument must be `str`, `int`, `float`, `bool`, `None`, `date`, `time`, `datetime`, `UUID`,
  `Decimal` or an enum of those. Anything else raises `TypeError` when you call the function:
  `argument 'filters' is a dict: pass key= with a template to name it, or to hash it, such as
  "{filters:blake2b}"`.

!!! note "Renaming a function changes its keys"

    The default key holds the function's name and module. After a deploy that renames or moves
    it, its old entries become misses and expire with their TTL. Use a template, such as
    `key="user:{user_id}"`, when the key has to survive a rename, or when another service or
    `redis-cli` reads it. A template is shorter in the backend too.

## A template

When a key has to survive a rename, or another service reads it, use a template. `key=` is a
`str.format` template over the arguments by name. A field can reach into an argument and take a
format spec:

=== "Sync"

    ```python title="app/users.py" hl_lines="4 12 23 31"
    --8<-- "caching_functions/template_key_sync.py:show"
    ```

=== "Async"

    ```python title="app/users.py" hl_lines="4 9 17 22"
    --8<-- "caching_functions/template_key_async.py:show"
    ```

A field puts in the value's text, the way `str.format` does: no quotes, so `{lang}` is `ru`. It
only takes values whose text is the same in every process: `str`, `int`, `float`, `bool`, `None`,
`date`, `time`, `datetime`, `UUID`, `Decimal` and enums of those.

Any other value raises `TypeError` when you call the function. Why? An object's text may be its
memory address, and a set's order differs between processes. Each call or each process would then
store its own entry. Name a plain part of the value, such as `{user.id}`, or
[hash it](#digests-and-cachekey_for).

!!! warning "A template names everything the result depends on"

    With `key="orders"` on `get_orders(user_id)`, all users share one entry, and the second user
    gets the first user's orders. A key holds what the template names and nothing else.

A template puts a value in the key as it is. With `key="doc:{owner}:{name}"`, the calls
`("a:b", "c")` and `("a", "b:c")` share one entry. If a part comes from users and may hold the
separator, hash it, such as `{name:blake2b}`, so each call gets its own key.

pashe checks a template when you decorate the function. Each of these raises
`InvalidOptionsError` right away: a field that isn't a parameter, such as `{usr_id}` for
`user_id`; an unknown digest, such as `{query:hsah}`; and `hmac` on a cache without `key_secret`.

## Digests and `cache.key_for`

Some arguments shouldn't go in a key as they are: they're too long, they have no plain form, or
they must not be readable in the backend. Put a digest of them in the key instead:

| Template | Puts in the key | For |
| --- | --- | --- |
| `{query:blake2b}` | 128 bits of BLAKE2b | an argument too long for a key, or with no plain form, such as a dict of filters |
| `{query:sha256}` | 128 bits of SHA-256 | the same, where only FIPS algorithms are allowed |
| `{email:hmac}` | 128 bits of HMAC-SHA256 under `key_secret` | data that must not be readable in the backend |

`hmac` needs the cache's [`key_secret`][pashe.Cache(key_secret)], 16 bytes or more.
[`cache.key_for`][pashe.Cache.key_for] fills in a template the way the cache does, digests too.
Use it to find an entry yourself, such as with `redis-cli`.

=== "Sync"

    ```python hl_lines="6 15 20 27"
    --8<-- "caching_functions/digests_sync.py:show"
    --8<-- "caching_functions/digests_sync.py:calls"
    ```

=== "Async"

    ```python hl_lines="6 15 20 27"
    --8<-- "caching_functions/digests_async.py:show"
    --8<-- "caching_functions/digests_async.py:calls"
    ```

=== "Sync"

    ```python title="app/users.py" hl_lines="4 13"
    --8<-- "caching_functions/digest_keys_sync.py:show"
    ```

=== "Async"

    ```python title="app/users.py" hl_lines="4 9"
    --8<-- "caching_functions/digest_keys_async.py:show"
    ```

A digest hashes the value as canonical JSON, so equal values give one key in every process. The
second call passes the set in another order and still gets the same key, because a set is sorted
before hashing.

Canonical JSON holds:

- `str`, `int`, `float`, `bool`, `None`, lists and tuples, as JSON does;
- a dict with its keys sorted, and a set or a frozenset with its items sorted;
- a dataclass, as the dict of its fields;
- an enum as its value, `date`, `time` and `datetime` as ISO 8601, `UUID` and `Decimal` as text.

Any other value raises `TypeError`, and so does a dataclass whose fields point back to it:
`cannot hash a User into a key`. The template's other parts stay readable, and `invalidate` and
`set` find the entry the way calls do.

!!! warning "An ORM object doesn't go in a key"

    A SQLAlchemy model, or one from another ORM, has no plain form: its relationships are queries
    to the database, and they may point back to it. Put its id in the key, `key="orders:{user.id}"`.
    Better yet, pass the id itself to the cached function: `get_orders(user_id: int)`.

!!! warning "A plain digest doesn't hide data"

    Someone can find an email from its digest by hashing a list of emails. For personal data, use
    `hmac`: without the secret, the digest tells nothing.
