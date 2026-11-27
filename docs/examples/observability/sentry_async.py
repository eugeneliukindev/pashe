# --8<-- [start:show]
from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.contrib.sentry import SentryHook

# sentry_sdk.init(dsn=...) as the application does already
cache = AsyncCache(AsyncMemoryBackend(), hooks=[SentryHook()])
# --8<-- [end:show]
