# Writing your own backend

Subclass `Backend`, or `AsyncBackend`, and implement its abstract methods: `get_many`,
`set_many`, `set_if_absent`, `delete`, `incr`, `expire`, `ttl`, `delete_if_equals`,
`expire_if_equals`, `ping` and `close`. `get` and `set` work through the batch methods unless you
write faster ones. The cache passes their arguments by position, and `ttl` by name, so
the parameters may have names of your own.

Every method is used by some part of a cache: entries need the reads and writes, tags `incr`,
locks and the load lock of `Stampede.lock_for` `set_if_absent`, `delete_if_equals` and
`expire_if_equals`, rate limits `incr`, `expire` and `ttl`. Each must be atomic, as several
processes call it on the same key at once.

---

API reference: [`pashe.backends`](../../reference/backends.md).
