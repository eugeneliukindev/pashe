# Compressors

A compressor shrinks the bytes of the codec before they are stored: it saves memory in Redis and
bytes on the network, and costs CPU on every read and write.

| The problem | The compressor | Install |
| --- | --- | --- |
| values of kilobytes fill Redis and the network | [`GzipCompressor`](#gzipcompressor) | nothing |
| the same, faster for the same size | [`ZstdCompressor`](#zstdcompressor) | `"pashe[zstd]"` before Python 3.14 |
| a small value grows when it is compressed | [`min_size`](#small-values-are-stored-as-they-are) | nothing |
| an algorithm of your own | [a `Compressor` of your own](#a-compressor-of-your-own) | nothing |

A compressor belongs to a cache, as its [`compressor`][pashe.Cache(compressor)]; a cache without
one stores the bytes of the codec as they are.

## GzipCompressor

Values of kilobytes take memory in Redis and bytes on the network;
[`GzipCompressor`][pashe.compressors.GzipCompressor] shrinks them with nothing installed.

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

It uses `compression.zstd` of Python 3.14, or its backport before, which `"pashe[zstd]"`
installs.

## Small values are stored as they are

A list of one product is 87 bytes as MessagePack, and 96 bytes with zstd, 105 with gzip: the
header of the format outweighs what it saves. So a compressor compresses a value only from its
[`min_size`][pashe.compressors.GzipCompressor(min_size)], in bytes of the codec.

=== "Sync"

    ```python hl_lines="5"
    --8<-- "codecs/min_size_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="5"
    --8<-- "codecs/min_size_async.py:show"
    ```

A compressor keeps the result only if it is smaller; any other value is stored as it is, in the
same cache.

## A compressor of your own

For an algorithm none of these has, subclass [`Compressor`][pashe.compressors.Compressor]. Its
[`min_size`][pashe.compressors.Compressor.min_size] is `0` unless you set it, so it compresses
every value, the small ones too.

## How they compare

100 products as MessagePack, 8 693 bytes, shrink to 631 bytes with zstd and 844 with gzip, and
zstd is three times faster: see [Benchmarks](../deep-dive/benchmarks.md#compressors).
