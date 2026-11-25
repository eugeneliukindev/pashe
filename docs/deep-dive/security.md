# Security

## Pickle

Unpickling runs code chosen by the bytes, so whoever can write to Redis could run code in every
process that reads it. `PickleCodec` therefore signs every value with HMAC-SHA256 under its
secret, and a value whose signature does not match is a `CodecError`, never unpickled. Keep the
secret out of Redis and the same in every process.

The signature is checked after the compressor decompressed the value, and decompression has no
limit: whoever can write to Redis can still make a reader decompress a few kilobytes into
gigabytes. Let only your services write to it.

## Personal data in keys

Keys are visible to whoever can run `SCAN` or `MONITOR` on Redis, and they end up in its logs.
An email, a phone number or a token in a key is personal data stored in the clear. Put it in a
template as `{email:hmac}`: the key then holds an HMAC-SHA256 under `key_secret`, which, unlike a
plain digest, cannot be found again by hashing a list of guesses. Keep the secret out of Redis
and the same in every process; changing it makes every such key a miss, which is safe.

## HTTP caching

`CacheHeadersMiddleware` sends `Cache-Control: private` by default: cached data may belong to
one user, and `public` would let shared caches and proxies hand it to another. Use `public` only
for responses that are the same for everyone.

The ETag is a hash of the response body, so a `304` is right whatever else the response holds;
it never tells two users apart by itself, as the body of each user differs.

## Rate limits

A failing backend lets a rate-limited call through by default, so an outage of Redis does not
take the service down. For limits that guard against abuse, such as logins, pass
`fail_open=False`: the call then raises `BackendError`.

The key of a limit is yours to choose. Behind a proxy, the address of the connection is the
address of the proxy: take the client from a header your proxy sets.

## Services that share a Redis

The prefix of a cache is put in front of every key, its own included, so services that share
a Redis do not see each other's entries. Its own keys live under `prefix + "__"`: keys of yours
must not start with `"__"`.
