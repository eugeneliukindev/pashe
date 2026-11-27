from pashe import AsyncCache
from pashe.backends import AsyncMemcachedBackend

cache = AsyncCache(AsyncMemcachedBackend("localhost", port=11211))
