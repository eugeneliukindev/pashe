"""The locks that Locks and AsyncLocks of pashe give: held in the backend, for every process over it."""

from pashe._internal.async_.locks.lock import AsyncLock
from pashe._internal.sync.locks.lock import Lock

__all__ = ["AsyncLock", "Lock"]
