from pashe import Cache
from pashe.backends import MemcachedBackend

cache = Cache(MemcachedBackend("localhost", port=11211))
