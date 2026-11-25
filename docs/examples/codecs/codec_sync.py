# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.msgspec import MsgspecJsonCodec

backend = MemoryBackend()


cache = Cache(backend, codec=MsgspecJsonCodec())


# --8<-- [end:show]
