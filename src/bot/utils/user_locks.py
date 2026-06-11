"""
Per-user asyncio locks for serializing concurrent callback handling.

The customer bot runs on a single event loop, so an asyncio.Lock keyed by
Telegram user id prevents double-tap races (e.g. two payment-link creations)
without blocking other users.
"""
import asyncio

_user_locks: dict[int, asyncio.Lock] = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    """Return a stable asyncio.Lock for the given user id, creating it on first use."""
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock
