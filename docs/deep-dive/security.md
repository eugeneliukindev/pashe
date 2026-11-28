# Security

## Pickle

Unpickling runs code that the bytes choose. So anyone who can write to Redis could run code in
every process that reads from it.

That's why `PickleCodec` signs every value with HMAC-SHA256 under its secret. If a value's
signature doesn't match, you get a `CodecError`, and the value is never unpickled. Keep the
secret out of Redis, and use the same one in every process.

The signature is checked after the compressor has decompressed the value, and decompression has
no limit. So anyone who can write to Redis can still make a reader decompress a few kilobytes
into gigabytes. Let only your own services write to it.

## Personal data in keys

Anyone who can run `SCAN` or `MONITOR` on Redis sees your keys, and keys end up in Redis logs. An
email, a phone number or a token in a key is personal data stored in the clear.

Put it in a template as `{email:hmac}` instead. The key then holds an HMAC-SHA256 under
`key_secret`. Unlike a plain digest, nobody can find the original by hashing a list of guesses.
Keep the secret out of Redis, and use the same one in every process. If you change it, every
such key becomes a miss, which is safe.

## HTTP caching

`CacheHeadersMiddleware` sends `Cache-Control: private` by default. Cached data can belong to one
user, and `public` would let shared caches and proxies hand it to someone else. Use `public` only
for responses that are the same for everyone.

The ETag is a hash of the response body, so a `304` is correct whatever else the response holds.
It never mixes up two users on its own, since each user's body differs.

## Rate limits

By default, a failing backend lets a rate-limited call through, so a Redis outage doesn't take
your service down. For limits that guard against abuse, such as logins, pass `fail_open=False`:
the call then raises `BackendError`.

You choose the key of a limit. Behind a proxy, the connection's address is the proxy's address,
so take the client from a header your proxy sets.

## Services that share a Redis

A cache puts its prefix in front of every key, including its own internal ones. So services that
share a Redis don't see each other's entries. The cache's own keys live under `prefix + "__"`, so
your keys must not start with `"__"`.
