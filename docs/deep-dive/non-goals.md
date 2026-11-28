# What pashe doesn't do

pashe caches function results for services that run as many processes. It also brings what such a
cache needs around it: locks, rate limits, near caches, tags and HTTP caching headers.

A cache can lose what it keeps, and that's fine: a miss only costs a load. Anything that needs
more than that belongs to a tool made for it.

| Not in pashe | Why | Use instead |
| --- | --- | --- |
| Data you can't lose | A cache drops entries on purpose: on eviction, when Redis restarts, when a deploy changes a type | your database |
| Idempotent writes, such as payments | A lost entry would run the write twice. You need storage that doesn't evict, and that refuses the write when it's down | a unique key in the database, in the write's transaction |
| Queues and background jobs | pashe runs a reload in the background of your process, not jobs that have to outlive it | Celery, arq, RQ, Dramatiq |
| Retries and circuit breakers around your services | The function is yours. pashe calls it, and returns a stale result while it fails | tenacity, stamina |
| Caching every ORM query on its own | Such a tool guesses what a write changes from the tables it touches. pashe caches the functions you pick, with the tags you name | django-cachalot, django-cacheops |
| A cache of whole responses in front of your application | That's a proxy or a CDN. pashe adds the headers they read | nginx, Varnish, a CDN |
| Sessions, and per-user data you keep for long | A session has to survive an eviction | your framework's session store |
| Redis data structures: queues, Bloom filters, leaderboards | Each one has its own guarantees and commands | redis-py, pottery |
| Strong consistency between the cache and the database | A cache that returns results without asking the database lags behind it for a moment. Tags and short TTLs keep that moment short | read from the database where the data has to be current |

!!! tip "Locks and rate limits are best effort too"

    A lock expires if its holder dies. A rate limit lets calls through when the backend fails,
    unless you pass `fail_open=False`. They protect you from doing the same work twice and from
    floods of calls. They don't protect you from a race that would corrupt data: use a database
    transaction for that.
