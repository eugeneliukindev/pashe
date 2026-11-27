# Troubleshooting

These are the errors you'll likely meet first, and what they mean. Every error pashe raises is
a subclass of `PasheError` from `pashe.errors`, so `except PasheError` catches them all.

??? question "TypeError: argument 'filters' is a dict: pass key= with a template"

    Without a template, the key is the function's name and the `repr` of its arguments. That
    `repr` reads the same in every process only for `str`, `int`, `float`, `bool`, `None`,
    `date`, `time`, `datetime`, `UUID`, `Decimal` and enums of those. Name the part that matters,
    or hash the whole argument:

    ```python
    --8<-- "troubleshooting/keys.py"
    ```

??? question "TypeError: a value of User has no text that is the same in every process"

    A template field without a digest, such as `{user}`, accepts the same types as the default
    key. An object's text may be its memory address, so every call would store its own entry. Name
    a plain part of it, like `{user.id}`. Better yet, pass the id to the cached function.

??? question "InvalidOptionsError: 'user:{usr_id}' names {usr_id}: get_user has no such parameter"

    pashe checks a template when you decorate the function: every field has to name one of the
    function's parameters. Fix the name, for example to `{user_id}`.

<!-- vale Pashe.Contractions = NO -->

??? question "TypeError: get_user is not async: cache it with Cache"

    `AsyncCache` caches `async def` functions, and `Cache` caches `def` ones. If you decorate a
    function of the other side, the decorator refuses it. Why so early? Awaiting a sync result, or
    calling an async one without awaiting it, would fail later and less clearly.

<!-- vale Pashe.Contractions = YES -->

??? question "InvalidOptionsError: JsonCodec reads User back as another type"

    The default `JsonCodec` reads back only what JSON can hold. So if a function returns a
    dataclass or a model, the decorator refuses it. Return a `TypedDict`, or give the cache a codec
    that rebuilds types from the return annotation: `MsgspecJsonCodec`, `MsgspecMsgpackCodec` or
    `PydanticCodec`. See [Recommended setup](recommended-setup.md).

<!-- vale Pashe.Contractions = NO -->

??? question "InvalidOptionsError: get_user is annotated with User, which is not defined yet"

    The cache reads a function's annotations when it decorates it, so it knows which type to
    rebuild. Define or import the class above the function, and not only under `TYPE_CHECKING`.

<!-- vale Pashe.Contractions = YES -->

??? question "After a deploy that changed a type, old entries are misses"

    That's on purpose. An entry remembers the shape of the type it was stored as: its classes
    and fields. When the shape changes, the entry turns into a miss and reloads, instead of
    decoding into the wrong shape.

??? question "I changed a cached result and another caller saw the change"

    With `Stampede(share_loads=True)`, the default, callers that miss the same key at once share
    one load, so they get the same object. Copy a result before you change it, or pass
    `stampede=Stampede(share_loads=False)` for that function.

??? question "InvalidOptionsError: ttl is 0 and no Stale window is set"

    `ttl=0` keeps a result only for its stale windows. Without any window, nothing would ever be
    stored. Give the function a positive `ttl`, or a window such as `Stale(while_revalidate=30)`.

??? question "InvalidOptionsError: a batch shares no loads, waits for its load and reloads nothing in the background"

    A batch loads its missing items in one call, and that call waits for the load. So a batch
    refuses anything that waits for another load or reloads in the background:
    `Stale(while_revalidate=...)`, `Stale(if_slow=...)`, `Stampede(lock_for=...)` and
    `Stampede(revalidate_before=...)`. The error names the ones you gave it.
    `Stale(if_error=...)` works.

??? question "InvalidOptionsError: redis: a backend needs a client without decode_responses"

    A backend stores bytes, and the codec decides what they mean. Create the client without
    `decode_responses=True`, which is what `Redis.from_url(url)` does by default.

??? question "InvalidOptionsError: redis: a backend needs a client with socket_timeout"

    Without a timeout, a call to a Redis that hangs waits as long as Redis hangs. No error comes,
    so neither the fallback nor a `CircuitBreaker` steps in. Give the client a timeout, such as
    `Redis.from_url(url, socket_timeout=1)`. A redis-py 8 client has a 5 second timeout unless you
    pass `socket_timeout=None`. Before version 8, a client has none.

??? question "OverloadedError"

    `Stampede.max_loads` is reached, and a stale result could answer the call instead. With a
    stale window, the cache answers with that result. Without one, the call waits for a slot
    instead of raising.

??? question "LockLostError"

    The lock expired while its block was running, so someone else may hold it now. pashe extends
    a lock every third of its `ttl`, so you lose it only when Redis was unreachable for longer than
    that. Give the lock a longer `ttl`, and make the block's work safe to run twice.

??? question "NotFoundError"

    The function raised one of the errors in `Negative.on`, either now or when the answer was
    cached. When it has just loaded, the function's error is the `__cause__`. A cached "not
    found" has none.
