"""
Database model enums.
"""

from enum import Enum


class DeliveryType(str, Enum):
    """Product delivery type."""

    PRE_UPLOADED = "pre_uploaded"
    SUPPLIER_BASED = "supplier_based"
    UPGRADE = "upgrade"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class SupplierOrderStatus(str, Enum):
    """Supplier order status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class TopupStatus(str, Enum):
    """Topup order status."""

    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class BalanceTxKind(str, Enum):
    """Balance transaction kind."""

    TOPUP = "topup"
    ORDER_PAYMENT = "order_payment"
    ADMIN_ADD = "admin_add"
    ADMIN_SUBTRACT = "admin_subtract"
    ADMIN_SET = "admin_set"
    REFUND = "refund"
