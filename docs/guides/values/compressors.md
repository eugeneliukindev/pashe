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

The same 100 products as MessagePack, 10 178 bytes:

| Compressor | Bytes | Compress, us | Decompress, us |
| --- | ---: | ---: | ---: |
| none | 10 178 | 0 | 0 |
| `ZstdCompressor(level=3)` | 1 124 | 20 | 7 |
| `GzipCompressor(level=6)` | 1 107 | 80 | 13 |
| `GzipCompressor(level=1)` | 1 232 | 30 | 13 |

zstd is four times faster than gzip for the same size. A compressor saves memory in Redis and
bytes on the network; it costs CPU on every read and write.

!!! tip "Small values are stored as they are"

    One product is 102 bytes as MessagePack, and 111 bytes with zstd, 120 with gzip: the
    header of the format outweighs what it saves. So a compressor compresses a value from its
    `min_size`, 1024 bytes by default, and keeps the result only if it is smaller; any other
    value is stored as it is, in the same cache. `min_size=0` compresses every value.

    ```python
    Cache(backend, compressor=GzipCompressor(min_size=4096))
    ```

---

API reference: [`pashe.compressors`](../../reference/compressors.md).
