# Troubleshooting

The errors you meet first, and what they mean.

??? question "TypeError: argument 'filters' is a dict: pass key= with a template"

    Without a template the key is the name of the function and the `repr` of its arguments,
    which is the same in every process only for `str`, `int`, `float`, `bool`, `None`, `date`,
    `time`, `datetime`, `UUID`, `Decimal` and enums of those. Name the part that matters, or
    hash the whole argument:

    ```python
    --8<-- "troubleshooting/keys.py"
    ```

??? question "TypeError: a value of User has no text that is the same in every process"

    A field of a template without a digest, such as `{user}`, takes the same types as the
    default key: the text of an object may be its address, so every call would store an entry of
    its own. Name a plain part of it, `{user.id}`, or better pass the cached function the id.

??? question "InvalidOptionsError: 'user:{usr_id}' names {usr_id}: get_user has no such parameter"

    A template is checked when the function is decorated: every field must name a parameter of
    the function. Fix the name, such as `{user_id}`.

??? question "TypeError: get_user is not async: cache it with a Cache"

    `AsyncCache` caches `async def` functions and `Cache` caches `def` ones. A function of the
    other side is refused when it is decorated, as awaiting a sync result, or calling an async
    one without awaiting it, would fail later and less clearly.

??? question "InvalidOptionsError: JsonCodec reads User back as another type"

    The default `JsonCodec` reads back what JSON holds, so a function that returns a dataclass
    or a model is refused when it is decorated. Return a `TypedDict`, or give the cache a codec
    that rebuilds types from the return annotation: `MsgspecJsonCodec`, `MsgspecMsgpackCodec` or
    `PydanticCodec`. See [Recommended setup](recommended-setup.md).

??? question "InvalidOptionsError: get_user is annotated with User, which is not defined yet"

    The cache reads the annotations of a function when it decorates it, to know the type to
    rebuild. Define or import the class above the function, and not only under `TYPE_CHECKING`.

??? question "After a deploy that changed a type, old entries are misses"

    That is on purpose. An entry remembers the shape of the type it was stored as: its classes
    and fields. When the shape changes, the entry is a miss and loads again, instead of decoding
    into the wrong form.

??? question "I changed a cached result and another caller saw the change"

    With `Stampede(single_flight=True)`, the default, concurrent callers of a key share one load
    and get the same object. Copy a result before you change it, or pass
    `stampede=Stampede(single_flight=False)` for that function.

??? question "InvalidOptionsError: ttl is 0 and no Stale window is set"

    `ttl=0` keeps a result only for its stale windows; with none, nothing would ever be stored.
    Give the function a positive `ttl` or a window such as `Stale(while_revalidate=30)`.

??? question "InvalidOptionsError: redis: a backend needs a client without decode_responses"

    A backend stores bytes: the codec decides what they mean. Create the client without
    `decode_responses=True`, as `Redis.from_url(url)` does by default.

??? question "OverloadedError"

    `Stampede.max_concurrent_loads` is reached and a stale result can answer the call instead.
    With a stale window the cache answers with it; without one, the call waits for a slot instead
    of raising.

??? question "LockLostError"

    The lock expired while its block ran: someone else may hold it now. It is extended every
    third of its `ttl`, so it is lost only when Redis was unreachable for longer than that. Give
    the lock a longer `ttl`, and keep the work of the block safe to run twice.

??? question "NotFoundError"

    The function raised one of `Negative.on`, now or when the answer was cached. The loader
    error is the `__cause__` when it just loaded; a cached "not found" has none.
