# Writing your own backend

Subclass [`Backend`][pashe.backends.Backend], or [`AsyncBackend`][pashe.backends.AsyncBackend], and
implement its abstract methods: `get_many`, `set_many`, `set_if_absent`, `delete`, `incr`, `expire`,
`ttl`, `delete_if_equals`, `expire_if_equals`, `ping` and `close`. `get` and `set` go through the
batch methods unless you write faster ones. The cache passes arguments by position, and `ttl` by
name, so you can name the other parameters as you like.

Some part of a cache uses every method:

- entries need the reads and writes;
- tags need `incr`;
- locks, and the load lock of `Stampede.lock_for`, need `set_if_absent`, `delete_if_equals` and
  `expire_if_equals`;
- rate limits need `incr`, `expire` and `ttl`.

Each method has to be atomic, because several processes call it on the same key at once.
