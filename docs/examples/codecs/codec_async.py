# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec

backend = AsyncMemoryBackend()


cache = AsyncCache(backend, codec=MsgspecJsonCodec())


# --8<-- [end:show]
