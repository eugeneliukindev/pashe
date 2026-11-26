# Caches

`pashe` exports the caches and the types of what they decorate, the locks and the rate limiter.
The async classes have the same methods as the sync ones, awaited.

::: pashe.Cache

::: pashe.AsyncCache

::: pashe.CachedFunction
    options:
      merge_init_into_class: false  # made by the cache, not by hand

::: pashe.AsyncCachedFunction
    options:
      merge_init_into_class: false  # made by the cache, not by hand

::: pashe.CachedBatchFunction
    options:
      merge_init_into_class: false  # made by the cache, not by hand

::: pashe.AsyncCachedBatchFunction
    options:
      merge_init_into_class: false  # made by the cache, not by hand

::: pashe.CachedValue
    options:
      merge_init_into_class: false  # made by the cache, not by hand

::: pashe.AsyncCachedValue
    options:
      merge_init_into_class: false  # made by the cache, not by hand

::: pashe.no_cache

::: pashe.Locks

::: pashe.AsyncLocks

::: pashe.RateLimiter

::: pashe.AsyncRateLimiter
