# What pashe does not do

pashe caches the results of functions for services that run as many processes, with what such a
cache needs around it: locks, rate limits, near caches, tags and the headers of HTTP caching. A
cache may lose what it keeps: a miss only costs a load. What needs more than that is left to tools
made for it.

| Not in pashe | Why | Take instead |
| --- | --- | --- |
| Data that must not be lost | A cache drops entries on purpose, on eviction, on a restart of Redis, on a deploy that changes a type | your database |
| Idempotency of writes, as of payments | A lost entry would run the write twice: it needs storage that does not evict, and a refusal when it is down | a unique key in the database, in the transaction of the write |
| Queues and background jobs | pashe runs a reload in the background of the process, not jobs that must outlive it | Celery, arq, RQ, Dramatiq |
| ReconnectBackoff and circuit breakers around your services | A loader is yours: pashe calls it, and answers with a stale result while it fails | tenacity, stamina |
| Caching every query of an ORM by itself | It guesses what a write changes from the tables it touches; pashe caches the functions you choose, with the tags you name | django-cachalot, django-cacheops |
| A cache in front of the application, of whole responses | That is a proxy or a CDN; pashe adds the headers they read | nginx, Varnish, a CDN |
| Sessions, and data kept per user for long | A session must outlive an eviction | the session store of your framework |
| Data structures in Redis: queues, Bloom filters, leaderboards | Each has its own guarantees and commands | redis-py, pottery |
| Strong consistency between the cache and the database | A cache that answers without the database is behind it for a moment; tags and short TTLs keep the moment short | read from the database where it must be current |

!!! tip "Locks and rate limits are best effort too"

    A lock expires if its holder dies, and a rate limit lets calls through when the backend
    fails, unless `fail_open=False`. They guard against doing the same work twice and against
    floods, not against a race that would corrupt data: for that, a transaction of the database.
