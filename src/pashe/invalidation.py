"""Invalidation buses: tell the other near caches which keys changed.

A NearCacheBackend of pashe.backends takes one as ``bus``; only key names travel. Subclass
InvalidationBus, or AsyncInvalidationBus, for a transport of your own; pashe.contrib.redis
has two: over Redis pub/sub, and with CLIENT TRACKING.
"""

from pashe._internal.async_.backends.near import AsyncInvalidationBus, AsyncInvalidationHandler, AsyncNoOpBus
from pashe._internal.sync.backends.near import InvalidationBus, InvalidationHandler, NoOpBus

__all__ = [
    "AsyncInvalidationBus",
    "AsyncInvalidationHandler",
    "AsyncNoOpBus",
    "InvalidationBus",
    "InvalidationHandler",
    "NoOpBus",
]
