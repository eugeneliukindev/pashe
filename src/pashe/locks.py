"""Locks held in the backend: every cache over it sees them."""

from pashe._internal.async_.locks.lock import AsyncLock
from pashe._internal.sync.locks.lock import Lock

__all__ = ["AsyncLock", "Lock"]
