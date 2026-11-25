# Examples

The code of an online shop, from its first cached query to a service of many processes. The
examples build on each other, as the modules of one application do. Pick **Sync** or **Async**
once: every example on every page switches with it.

The diagram above each example tells what it does: yellow answers from the cache, blue reaches
the source, and a box is a process or Redis, as [Core concepts](concepts.md#processes) shows.

## The shop

`db` is the connection to the database of the shop: `sqlite3` on the sync side, `aiosqlite` on
the async one. `partner` and `payments` are `httpx` clients of the APIs the shop calls.

=== "Sync"

    ```python
    --8<-- "shop/shop_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "shop/shop_async.py"
    ```

`MsgspecJsonCodec` rebuilds a `Product` from the return annotation of a cached function; the
default `JsonCodec` would hand back a `dict`.

## 1. A slow query

A product page reads its product from the database on every request. Cache it for five minutes:

```mermaid
sequenceDiagram
    participant Page
    participant Cache
    participant DB as Database
    Page->>Cache: get_product(1)
    Cache->>DB: miss, query
    DB-->>Cache: product, stored for 300 s
    Cache-->>Page: product
    Page->>Cache: get_product(1)
    Cache-->>Page: hit, the database is not asked
```

=== "Sync"

    ```python
    --8<-- "shop/slow_query_sync.py:show"
    --8<-- "shop/slow_query_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/slow_query_async.py:show"
    --8<-- "shop/slow_query_async.py:calls"
    ```

```{.text title="Queries to the database"}
get_product(1)  1 query
get_product(1)  0 queries
```

## 2. Data that changes

A new price must show at once, on the product page and on every list of its category. Tag what
depends on what, and tell the cache when you write:

```mermaid
flowchart LR
    write(["change_price(1, 990)"]) --> set["get_product.set: product:1 holds the new price"]
    write --> tags["invalidate_tags: every list tagged category:coffee is dropped"]
    tags --> next["the next list_category loads again"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class set fromCache
    class next fromSource
```

=== "Sync"

    ```python
    --8<-- "shop/data_changes_sync.py:imports"
    --8<-- "shop/data_changes_sync.py:show"
    --8<-- "shop/data_changes_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/data_changes_async.py:imports"
    --8<-- "shop/data_changes_async.py:show"
    --8<-- "shop/data_changes_async.py:calls"
    ```

`set` stores the new product without a query; the tag drops every list of the category in one
write, however many there are.

## 3. A partner that fails

Prices show in the currency of the customer, and the rates come from a partner API that is down
now and then. A rate an hour old is better than an error page, and a currency the partner does
not know is not asked for again on every request:

```mermaid
flowchart LR
    fresh["fresh: HIT"] -- "ttl is over" --> load{"ask the partner"}
    load -- "rate" --> stored["store it: MISS"]
    load -- "httpx.HTTPError" --> stale["the last rate, for up to an hour: STALE_IF_ERROR"]
    load -- "UnknownCurrencyError" --> missing["NotFoundError, remembered for 10 min: NOT_FOUND"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class fresh,stale,missing fromCache
    class load,stored fromSource
```

=== "Sync"

    ```python
    --8<-- "shop/partner_sync.py:imports"
    --8<-- "shop/partner_sync.py:show"
    --8<-- "shop/partner_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/partner_async.py:imports"
    --8<-- "shop/partner_async.py:show"
    --8<-- "shop/partner_async.py:calls"
    ```

A call for an unknown currency raises `NotFoundError`, from the cache the next ten minutes.

## 4. An expensive report under load

The sales report of a day takes seconds to build. When it expires, every admin who opens the
dashboard at that moment would start one:

```mermaid
sequenceDiagram
    box rgba(43,91,132,0.14) Process 1
        participant A as Admin 1
    end
    box rgba(0,150,136,0.14) Process 2
        participant B as Other admins
    end
    box rgba(247,181,0,0.18) Redis: every process
        participant R as Redis
    end
    participant DB as Database
    A->>R: miss, take the load lock
    B->>R: miss, the lock is taken: wait
    A->>DB: the only query
    A->>R: store the report, release the lock
    R-->>B: the same report
```

=== "Sync"

    ```python
    --8<-- "shop/report_sync.py:imports"
    --8<-- "shop/report_sync.py:show"
    --8<-- "shop/report_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/report_async.py:imports"
    --8<-- "shop/report_async.py:show"
    --8<-- "shop/report_async.py:calls"
    ```

## 5. A feed of many products

The home page shows fifty prices. Fifty cached calls are fifty round trips to the cache; a batch
function reads them in one and queries only the missing ones:

```mermaid
flowchart LR
    call(["get_prices([1, 2, 3])"]) --> read["one read of price:1, price:2 and price:3"]
    read -- "1, 2 stored" --> hit["from the cache"]
    read -- "3 missing" --> load["one query for 3"]
    load --> answer(["the three prices"])
    hit --> answer
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class hit fromCache
    class load fromSource
```

=== "Sync"

    ```python
    --8<-- "shop/feed_sync.py:show"
    --8<-- "shop/feed_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/feed_async.py:show"
    --8<-- "shop/feed_async.py:calls"
    ```

```{.text title="Queries to the database"}
get_prices([1, 2])     1 query
get_prices([1, 2, 3])  1 query
```

## 6. A token that says how long it lives

The payment provider hands out access tokens and says how long each is valid. Keep each that
long, less a minute of margin:

```mermaid
flowchart LR
    provider["the provider: expires_in = 3600"] --> ttl["ttl = expires_in - 60"]
    ttl --> stored["the token is reused for 3540 s"]
    stored -- "then" --> renewed["a new token, before the old one expires"]
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class stored fromCache
    class provider,renewed fromSource
```

=== "Sync"

    ```python
    --8<-- "shop/token_sync.py:imports"
    --8<-- "shop/token_sync.py:show"
    --8<-- "shop/token_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/token_async.py:imports"
    --8<-- "shop/token_async.py:show"
    --8<-- "shop/token_async.py:calls"
    ```

## 7. Logins, quotas and a nightly job

Every process of the shop shares the limits and the locks, as they live in the backend:

```mermaid
flowchart LR
    backend[("the backend, shared by every process")]
    login["5 failed logins in 15 min"] -- "6th" --> ban["RateLimitedError, retry_after = 1 h"]
    partner["a partner over 100 searches a minute"] --> limited["RateLimitedError"]
    job["the nightly export on every server"] -- "try_lock" --> one["one runs it, the others skip"]
    ban & limited & one -.- backend
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class ban,limited,one fromCache
```

=== "Sync"

    ```python
    --8<-- "shop/limits_sync.py:imports"
    --8<-- "shop/limits_sync.py:show"
    --8<-- "shop/limits_sync.py:calls"
    ```

=== "Async"

    ```python
    --8<-- "shop/limits_async.py:imports"
    --8<-- "shop/limits_async.py:show"
    --8<-- "shop/limits_async.py:calls"
    ```

## 8. A web service

The product page over HTTP, with the headers of caching and a quota per client:

```mermaid
sequenceDiagram
    participant Client
    participant MW as CacheHeadersMiddleware
    participant App as product_page
    Client->>MW: GET /products/1
    MW->>App: product_page(1)
    App-->>MW: body, from get_product with 300 s left
    MW-->>Client: 200, ETag, Cache-Control private max-age
    Client->>MW: GET /products/1, If-None-Match
    MW->>App: request
    App-->>MW: the same body
    MW-->>Client: 304, without the body
```

=== "Sync"

    ```python hl_lines="6 12 25"
    --8<-- "shop/web_sync.py:imports"
    --8<-- "shop/web_sync.py:show"
    ```

=== "Async"

    ```python hl_lines="6 12 25"
    --8<-- "shop/web_async.py:imports"
    --8<-- "shop/web_async.py:show"
    ```

A second request with the `ETag` of the first in `If-None-Match` gets `304`, without the body:

```{.console title="Two requests to the service" hl_lines="5 6 7 11"}
$ curl -i http://localhost:8000/products/1
HTTP/1.1 200 OK
content-length: 68
content-type: application/json
etag: "558ab5fd04ed91e5448d53a2115d8dfb"
cache-control: private, max-age=299
cache-status: pashe; hit; ttl=299

{"id":1,"name":"Coffee beans","category":"coffee","price_cents":990}
$ curl -i http://localhost:8000/products/1 -H 'If-None-Match: "558ab5fd04ed91e5448d53a2115d8dfb"'
HTTP/1.1 304 Not Modified
etag: "558ab5fd04ed91e5448d53a2115d8dfb"
cache-control: private, max-age=299
cache-status: pashe; hit; ttl=299
```

## 9. Many processes in production

Every worker of every server shares Redis, keeps hot entries in its own memory for five seconds
and answers from a fallback while Redis is down:

```mermaid
flowchart LR
    subgraph p1["Process 1, a worker"]
        request(["a call"]) --> local["its memory, 5 s"]
        fallback["the fallback in memory"]
    end
    subgraph shared["Redis: every process"]
        redis[("entries")]
    end
    source["the function"]
    local -- "miss" --> redis
    redis -- "miss" --> source
    redis -. "down" .-> fallback
    redis -. "a write elsewhere drops the copy" .-> local
    style p1 fill:#2b5b8424,stroke:#2b5b84
    style shared fill:#f7b5002e,stroke:#c98f00
    classDef fromCache fill:#f7b500,color:#000000,stroke:#c98f00
    classDef fromSource fill:#2b5b84,color:#ffffff,stroke:#1f4466
    class local,redis,fallback fromCache
    class source fromSource
```

=== "Sync"

    ```python
    --8<-- "shop/production_sync.py"
    ```

=== "Async"

    ```python
    --8<-- "shop/production_async.py"
    ```
