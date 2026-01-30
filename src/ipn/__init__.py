"""
IPN (Instant Payment Notification) package.

Shared order fulfillment logic used by all payment providers (PayOS, Pay2S, etc.).
Webhooks call the processor with order_id, transaction_id, and amount; the processor
updates order status, sends delivery, and notifies users/suppliers.
"""
from src.ipn.processor import (
    IPNOrderProcessor,
    get_ipn_processor,
    get_global_customer_bot,
    set_global_bot,
    set_global_supplier_bot,
)

__all__ = [
    "IPNOrderProcessor",
    "get_ipn_processor",
    "get_global_customer_bot",
    "set_global_bot",
    "set_global_supplier_bot",
]
