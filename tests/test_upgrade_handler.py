"""Regression tests for UPGRADE Done handling helpers."""
from types import SimpleNamespace

from src.bot.handlers.upgrade_handler import _has_upgrade_item
from src.database.models.enums import DeliveryType


def test_has_upgrade_item_when_upgrade_is_not_first() -> None:
    """Mixed orders must retain access to the Done action."""
    order = SimpleNamespace(
        items=[
            SimpleNamespace(product=SimpleNamespace(delivery_type=DeliveryType.PRE_UPLOADED)),
            SimpleNamespace(product=SimpleNamespace(delivery_type=DeliveryType.UPGRADE)),
        ]
    )

    assert _has_upgrade_item(order) is True


def test_has_upgrade_item_rejects_orders_without_upgrade_products() -> None:
    order = SimpleNamespace(
        items=[SimpleNamespace(product=SimpleNamespace(delivery_type=DeliveryType.PRE_UPLOADED))]
    )

    assert _has_upgrade_item(order) is False
