# Benchmarks

What a codec, a compressor and a call of the cache cost, as `benchmarks/` of the repository
measures them. Run them with `just bench`: it prints the times, then the bytes each codec and
compressor made. Every other run of the tests takes each benchmark once, as a test. Your numbers
will differ, the ratios hold.

The numbers below: the median of many rounds, in microseconds. Python 3.15.1 on an Intel Core
i9-9900KF, Linux; Redis 8 and a Redis Cluster in Docker on the same machine; msgspec 0.22,
orjson 3.13, pydantic 2.14, redis-py 8.1.

## What is stored

The codecs and the compressors store products of a shop, in three sizes: one product, a small
entry; 100, a page or a list; and 10 000, a big report, about the most worth caching.

```python
--8<-- "benchmarks/products.py"
```

## Codecs

Each codec encodes the products and decodes them back as the type of the cached function:
`list[Product]` for a codec that rebuilds your types, a list of `dict`s for one of plain JSON.

| Codec | Bytes: 1 | 100 | 10 000 |
| --- | ---: | ---: | ---: |
| `MsgspecMsgpackCodec` | 87 | 8 693 | 908 509 |
| `PickleCodec` | 198 | 5 734 | 588 868 |
| the codecs of JSON | 117 | 11 715 | 1 212 405 |

| Codec | Encode, us: 1 | 100 | 10 000 | Decode, us: 1 | 100 | 10 000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `OrjsonCodec` | 0.25 | 11 | 984 | 0.64 | 38 | 5 492 |
| `MsgspecMsgpackCodec` | 0.34 | 18 | 1 682 | 1.0 | 41 | 5 575 |
| `MsgspecJsonCodec` | 0.41 | 18 | 1 711 | 1.0 | 45 | 6 022 |
| `PydanticCodec` | 0.96 | 63 | 6 492 | 1.5 | 97 | 12 374 |
| `JsonCodec`, the default | 1.8 | 67 | 7 416 | 1.6 | 86 | 10 797 |
| `PickleCodec` | 4.4 | 76 | 7 791 | 4.7 | 80 | 9 803 |

## Compressors

Each compressor shrinks the products as MessagePack, 87, 8 693 and 908 509 bytes, and restores
them. One product grows: the header of the format outweighs what it saves, which is why a
compressor leaves a value under its `min_size` as it is.

| Compressor | Bytes: 1 | 100 | 10 000 |
| --- | ---: | ---: | ---: |
| none | 87 | 8 693 | 908 509 |
| `ZstdCompressor(level=3)` | 96 | 631 | 54 034 |
| `GzipCompressor(level=1)` | 105 | 958 | 83 574 |
| `GzipCompressor(level=6)` | 105 | 844 | 91 126 |

| Compressor | Compress, us: 1 | 100 | 10 000 | Decompress, us: 1 | 100 | 10 000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ZstdCompressor(level=3)` | 4.1 | 16 | 870 | 0.78 | 6.5 | 427 |
| `GzipCompressor(level=1)` | 4.8 | 21 | 1 836 | 0.69 | 9.0 | 803 |
| `GzipCompressor(level=6)` | 5.0 | 55 | 4 886 | 0.69 | 8.7 | 729 |

## A call of the cache

A cached function of one argument returns a small `TypedDict`, over each backend of `Cache`: a hit
answers from the cache, a miss runs the function and stores what it returned.

| Backend | Hit, us | Miss, us |
| --- | ---: | ---: |
| `MemoryBackend` | 10 | 24 |
| `SQLiteBackend` | 24 | 61 |
| `RedisBackend` | 93 | 225 |
| `RedisBackend` over a Redis Cluster | 95 | 213 |

Most of a call over Redis is its round trips, one for a hit and two for a miss: see
[What a call costs](cost.md). A near cache answers a hit from memory:
[Near cache](../guides/backends/near-cache.md).
