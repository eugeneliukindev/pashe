# --8<-- [start:show]
import logging

from pashe import AsyncCache
from pashe.backends import AsyncMemoryBackend
from pashe.hooks import LoggingHook

cache = AsyncCache(AsyncMemoryBackend(), hooks=[LoggingHook()])  # warnings to the logger "pashe"
reports = AsyncCache(AsyncMemoryBackend(), hooks=[LoggingHook(logger=logging.getLogger("app.reports"))])

logging.getLogger("pashe").setLevel(logging.ERROR)  # quieter: the warnings of the first cache go
# --8<-- [end:show]
