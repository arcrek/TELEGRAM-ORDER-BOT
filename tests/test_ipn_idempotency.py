"""
The IPN fulfillment lock helper must serialize per order id.
"""
import threading

from src.ipn.processor import _get_order_lock


def test_same_order_gets_same_lock():
    assert _get_order_lock("ORD-1") is _get_order_lock("ORD-1")


def test_different_orders_get_different_locks():
    assert _get_order_lock("ORD-A") is not _get_order_lock("ORD-B")


def test_lock_is_a_lock():
    lock = _get_order_lock("ORD-2")
    assert hasattr(lock, "acquire") and hasattr(lock, "release")
    # A threading.Lock is acquirable/releasable
    assert lock.acquire(blocking=False) is True
    lock.release()
