# Benchmarks

This page shows what a codec, a compressor and a cache call cost, as measured by the
repository's `benchmarks/`. Run them with `just bench`: it prints the times, then the bytes each
codec and compressor produced. Every other test run also runs each benchmark once, as a test.

Your numbers will differ, but the ratios hold.

## The machine

| Part | This run |
| --- | --- |
| CPU | Intel Core i9-9900KF, 3.6 GHz, 8 cores, 16 threads |
| OS | Linux 7.3 (CachyOS) |
| Python | 3.15.1 |
| Redis | Redis 8 and a Redis Cluster of 3 nodes, in Docker on the same machine |
| Libraries | msgspec 0.22, orjson 3.13, pydantic 2.14, redis-py 8.1 |
| How | the median of many rounds of pytest-benchmark, in one process |

Times are in microseconds (us, a millionth of a second), and sizes are in bytes. In each column
the <span class="pashe-best">best</span> is green, the <span class="pashe-second">second</span> is
yellow and the <span class="pashe-worst">worst</span> is red. Lower is better in every table.

## What is stored

The codecs and compressors store a shop's products, in three sizes. One product is a small
entry. 100 products are a page or a list. 10 000 products are a big report, about the most you'd
want to cache.

```python
--8<-- "benchmarks/products.py"
```

## Codecs

Each codec encodes the products and decodes them back as the cached function's type. A codec
that rebuilds your types returns `list[Product]`; a plain JSON codec returns a list of `dict`s.

### Bytes

| Codec | 1 product | 100 products | 10 000 products |
| --- | ---: | ---: | ---: |
| `MsgspecMsgpackCodec` | <span class="pashe-best">87</span> | <span class="pashe-second">8 693</span> | <span class="pashe-second">908 509</span> |
| `PickleCodec` | <span class="pashe-worst">198</span> | <span class="pashe-best">5 734</span> | <span class="pashe-best">588 868</span> |
| `OrjsonCodec` | <span class="pashe-second">117</span> | <span class="pashe-worst">11 715</span> | <span class="pashe-worst">1 212 405</span> |
| `MsgspecJsonCodec` | <span class="pashe-second">117</span> | <span class="pashe-worst">11 715</span> | <span class="pashe-worst">1 212 405</span> |
| `PydanticCodec` | <span class="pashe-second">117</span> | <span class="pashe-worst">11 715</span> | <span class="pashe-worst">1 212 405</span> |
| `JsonCodec`, the default | <span class="pashe-second">117</span> | <span class="pashe-worst">11 715</span> | <span class="pashe-worst">1 212 405</span> |

### Encode, us

| Codec | 1 product | 100 products | 10 000 products |
| --- | ---: | ---: | ---: |
| `OrjsonCodec` | <span class="pashe-best">0.25</span> | <span class="pashe-best">11</span> | <span class="pashe-best">984</span> |
| `MsgspecMsgpackCodec` | <span class="pashe-second">0.34</span> | <span class="pashe-second">18</span> | <span class="pashe-second">1 682</span> |
| `MsgspecJsonCodec` | 0.41 | <span class="pashe-second">18</span> | 1 711 |
| `PydanticCodec` | 0.96 | 63 | 6 492 |
| `JsonCodec`, the default | 1.8 | 67 | 7 416 |
| `PickleCodec` | <span class="pashe-worst">4.4</span> | <span class="pashe-worst">76</span> | <span class="pashe-worst">7 791</span> |

### Decode, us

| Codec | 1 product | 100 products | 10 000 products |
| --- | ---: | ---: | ---: |
| `OrjsonCodec` | <span class="pashe-best">0.64</span> | <span class="pashe-best">38</span> | <span class="pashe-best">5 492</span> |
| `MsgspecMsgpackCodec` | <span class="pashe-second">1</span> | <span class="pashe-second">41</span> | <span class="pashe-second">5 575</span> |
| `MsgspecJsonCodec` | <span class="pashe-second">1</span> | 45 | 6 022 |
| `PydanticCodec` | 1.5 | <span class="pashe-worst">97</span> | <span class="pashe-worst">12 374</span> |
| `JsonCodec`, the default | 1.6 | 86 | 10 797 |
| `PickleCodec` | <span class="pashe-worst">4.7</span> | 80 | 9 803 |

## Compressors

Each compressor shrinks the products, encoded as MessagePack, and restores them. One product
actually grows: the format's header outweighs what it saves. That's why a compressor leaves a
value under its `min_size` as it is.

### Bytes

| Compressor | 1 product | 100 products | 10 000 products |
| --- | ---: | ---: | ---: |
| none, as MessagePack | 87 | 8 693 | 908 509 |
| `ZstdCompressor(level=3)` | <span class="pashe-best">96</span> | <span class="pashe-best">631</span> | <span class="pashe-best">54 034</span> |
| `GzipCompressor(level=1)` | <span class="pashe-worst">105</span> | <span class="pashe-worst">958</span> | <span class="pashe-second">83 574</span> |
| `GzipCompressor(level=6)` | <span class="pashe-worst">105</span> | <span class="pashe-second">844</span> | <span class="pashe-worst">91 126</span> |

### Compress, us

| Compressor | 1 product | 100 products | 10 000 products |
| --- | ---: | ---: | ---: |
| `ZstdCompressor(level=3)` | <span class="pashe-best">4.1</span> | <span class="pashe-best">16</span> | <span class="pashe-best">870</span> |
| `GzipCompressor(level=1)` | <span class="pashe-second">4.8</span> | <span class="pashe-second">21</span> | <span class="pashe-second">1 836</span> |
| `GzipCompressor(level=6)` | <span class="pashe-worst">5</span> | <span class="pashe-worst">55</span> | <span class="pashe-worst">4 886</span> |

### Decompress, us

| Compressor | 1 product | 100 products | 10 000 products |
| --- | ---: | ---: | ---: |
| `ZstdCompressor(level=3)` | <span class="pashe-worst">0.78</span> | <span class="pashe-best">6.5</span> | <span class="pashe-best">427</span> |
| `GzipCompressor(level=1)` | <span class="pashe-best">0.69</span> | <span class="pashe-worst">9</span> | <span class="pashe-worst">803</span> |
| `GzipCompressor(level=6)` | <span class="pashe-best">0.69</span> | <span class="pashe-second">8.7</span> | <span class="pashe-second">729</span> |

## A call of the cache

A cached function with one argument returns a small `TypedDict`, over each `Cache` backend. A
hit is answered from the cache; a miss runs the function and stores what it returned.

### One call, us

| Backend | Hit | Miss |
| --- | ---: | ---: |
| `MemoryBackend` | <span class="pashe-best">10</span> | <span class="pashe-best">24</span> |
| `SQLiteBackend` | <span class="pashe-second">24</span> | <span class="pashe-second">61</span> |
| `RedisBackend` | 93 | <span class="pashe-worst">225</span> |
| `RedisBackend` over a Redis Cluster | <span class="pashe-worst">95</span> | 213 |

Over Redis, most of a call's time goes to its round trips: one for a hit and two for a miss.
See [What a call costs](cost.md). A near cache answers a hit from memory; see
[Near cache](../guides/near-cache.md).
