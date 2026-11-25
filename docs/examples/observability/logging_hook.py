# --8<-- [start:show]
import logging

from pashe import Cache
from pashe.backends import MemoryBackend
from pashe.hooks import LoggingHook

cache = Cache(MemoryBackend(), hooks=[LoggingHook()])  # warnings to the logger "pashe"
reports = Cache(MemoryBackend(), hooks=[LoggingHook(logger=logging.getLogger("app.reports"))])

logging.getLogger("pashe").setLevel(logging.ERROR)  # quieter: the warnings of the first cache go
# --8<-- [end:show]
