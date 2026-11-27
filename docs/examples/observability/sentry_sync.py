# --8<-- [start:show]
from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.contrib.sentry import SentryHook

# sentry_sdk.init(dsn=...) as the application does already
cache = Cache(MemoryBackend(), hooks=[SentryHook()])
# --8<-- [end:show]
