# Compressors

A compressor shrinks the bytes of the codec before they are stored:

=== "GzipCompressor"

    === "Sync"

        ```python
        --8<-- "codecs/gzip_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/gzip_async.py:show"
        ```

=== "ZstdCompressor"

    === "Sync"

        ```python
        --8<-- "codecs/zstd_sync.py:show"
        ```

    === "Async"

        ```python
        --8<-- "codecs/zstd_async.py:show"
        ```

`ZstdCompressor` of `pashe.contrib.zstd` is faster for the same size; it uses `compression.zstd`
of Python 3.14, or its backport before.

A cache without `compressor=` has `NoOpCompressor`, which stores the bytes of the codec as they
are. A compressor of your own subclasses `Compressor` of `pashe.compressors`: `compress` and
`decompress` turn bytes into bytes, and `min_size` is the length below which a value is stored as
it is.

## How they compare

100 products as MessagePack, 8 693 bytes, shrink to 631 bytes with zstd and 844 with gzip, and
zstd is three times faster: see [Benchmarks](../../deep-dive/benchmarks.md#compressors). A
compressor saves memory in Redis and bytes on the network; it costs CPU on every read and write.

!!! tip "Small values are stored as they are"

    A list of one product is 87 bytes as MessagePack, and 96 bytes with zstd, 105 with gzip: the
    header of the format outweighs what it saves. So a compressor compresses a value from its
    `min_size`, 1024 bytes by default, and keeps the result only if it is smaller; any other
    value is stored as it is, in the same cache. `min_size=0` compresses every value.

    ```python
    --8<-- "codecs/min_size.py"
    ```

---

API reference: [`pashe.compressors`](../../reference/compressors.md).
