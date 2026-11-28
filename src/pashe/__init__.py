"""Caching for Python services: stale results, stampede protection, tags, locks and rate limits.

The root holds what every user needs: the caches and the types of what they decorate, the locks
and the rate limiter. The rest lives in modules by topic: pashe.errors, pashe.ratelimit,
pashe.locks, pashe.hooks, and the packages of backends, invalidation buses, codecs and compressors.
"""

from importlib.metadata import version

from pashe._internal.async_.cache.cache import AsyncCache
from pashe._internal.async_.cache.cached import AsyncCachedFunction, AsyncCachedValue
from pashe._internal.async_.cache.cached_batch import AsyncCachedBatchFunction
from pashe._internal.async_.limiter import AsyncRateLimiter
from pashe._internal.async_.locks.locks import AsyncLocks
from pashe._internal.cache.call import no_cache
from pashe._internal.sync.cache.cache import Cache
from pashe._internal.sync.cache.cached import CachedFunction, CachedValue
from pashe._internal.sync.cache.cached_batch import CachedBatchFunction
from pashe._internal.sync.limiter import RateLimiter
from pashe._internal.sync.locks.locks import Locks

__version__ = version("pashe")

__all__ = [
    "AsyncCache",
    "AsyncCachedBatchFunction",
    "AsyncCachedFunction",
    "AsyncCachedValue",
    "AsyncLocks",
    "AsyncRateLimiter",
    "Cache",
    "CachedBatchFunction",
    "CachedFunction",
    "CachedValue",
    "Locks",
    "RateLimiter",
    "no_cache",
]
