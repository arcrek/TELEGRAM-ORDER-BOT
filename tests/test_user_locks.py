"""
Per-user asyncio locks for serializing payment callbacks.
"""
import asyncio

from src.bot.utils.user_locks import get_user_lock


def test_same_user_gets_same_lock():
    assert get_user_lock(111) is get_user_lock(111)


def test_different_users_get_different_locks():
    assert get_user_lock(222) is not get_user_lock(333)


def test_lock_is_asyncio_lock():
    assert isinstance(get_user_lock(444), asyncio.Lock)
