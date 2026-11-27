# Compressors

A compressor shrinks the codec's bytes before they're stored. You save memory in Redis and bytes
on the network, and you pay with CPU time on every read and write.

| The problem | The compressor | Install |
| --- | --- | --- |
| values of kilobytes fill Redis and the network | [`GzipCompressor`](#gzipcompressor) | nothing |
| the same, faster for the same size | [`ZstdCompressor`](#zstdcompressor) | `"pashe[zstd]"` before Python 3.14 |
| a small value grows when it's compressed | [`min_size`](#small-values-are-stored-as-they-are) | nothing |
| an algorithm of your own | [a `Compressor` of your own](#a-compressor-of-your-own) | nothing |

You give a compressor to a cache as its [`compressor`][pashe.Cache(compressor)]. Without one,
the cache stores the codec's bytes as they are.

## GzipCompressor

Values of a few kilobytes take memory in Redis and bytes on the network.
[`GzipCompressor`][pashe.compressors.GzipCompressor] shrinks them, and you don't need to install
anything.

=== "Sync"

    ```python hl_lines="6"
    --8<-- "codecs/gzip_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6"
    --8<-- "codecs/gzip_async.py:show"
    ```

## ZstdCompressor

[`ZstdCompressor`][pashe.contrib.zstd.ZstdCompressor] is faster than gzip for the same size.

=== "Sync"

    ```python hl_lines="6"
    --8<-- "codecs/zstd_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6"
    --8<-- "codecs/zstd_async.py:show"
    ```

It uses `compression.zstd` from Python 3.14. On older Pythons it uses the backport, which
`"pashe[zstd]"` installs.

## Small values are stored as they are

Compression can make a small value bigger. A list of one product is 87 bytes as MessagePack, but
96 bytes with zstd and 105 with gzip: the format's header costs more than it saves. That's why a
compressor only compresses values from its
[`min_size`][pashe.compressors.GzipCompressor(min_size)] up, counted in the codec's bytes.

=== "Sync"

    ```python hl_lines="5"
    --8<-- "codecs/min_size_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="5"
    --8<-- "codecs/min_size_async.py:show"
    ```

A compressor keeps the compressed bytes only if they're smaller. Every other value is stored as
it is, in the same cache.

## A compressor of your own

Need an algorithm none of these has? Subclass [`Compressor`][pashe.compressors.Compressor]. Watch
its [`min_size`][pashe.compressors.Compressor.min_size]: it's `0` unless you set it, so your
compressor compresses every value, small ones too.

## How they compare

100 products as MessagePack take 8 693 bytes. They shrink to 631 bytes with zstd and 844 with
gzip, and zstd is three times faster. See [Benchmarks](../deep-dive/benchmarks.md#compressors).
