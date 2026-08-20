"""
Read-only data service for the customer /export feature.

Builds what /export needs: which products/variants the requesting user has
delivered pre-uploaded content for, and the per-order delivered content lines.
Every query is scoped to the user's Telegram id, to DELIVERED orders, and to
used pre-uploaded rows — never return another user's delivered credentials.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models.enums import OrderStatus
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation

logger = logging.getLogger(__name__)


@dataclass
class ExportOrderEntry:
    order_id: str
    created_at: datetime
    price: int            # OrderItem.subtotal for this variant in this order
    quantity: int         # OrderItem.quantity
    bonus_quantity: int   # OrderItem.bonus_quantity
    contents: list = field(default_factory=list)  # list[str] delivered content lines


@dataclass
class ExportVariantData:
    product_id: str
    product_name: str
    variation_id: str
    variation_name: str
    orders: list = field(default_factory=list)  # list[ExportOrderEntry]

    @property
    def total_orders(self) -> int:
        return len(self.orders)

    @property
    def total_items(self) -> int:
        return sum(len(o.contents) for o in self.orders)


def _render_delivery_content(raw_data: str | None) -> str:
    """Render one PreUploadedProduct.product_data exactly the way the delivery
    flow shows it to the customer (mirrors src/ipn/processor.py)."""
    if not raw_data:
        return "[No delivery data available]"
    try:
        parsed = json.loads(raw_data)
    except (json.JSONDecodeError, TypeError):
        return raw_data  # plain text
    if isinstance(parsed, dict):
        if not parsed:
            return "[No delivery data available]"
        if "delivery_data" in parsed and len(parsed) == 1:
            return str(parsed["delivery_data"])
        if "value" in parsed and len(parsed) == 1:
            return str(parsed["value"])
        return "\n".join(f"{k}: {v}" for k, v in parsed.items())
    return str(parsed)  # JSON scalar


class ExportService:
    """Read-only queries for the /export feature."""

    def __init__(self, session: Session):
        self.session = session

    def get_exportable_products(self, user_id: int) -> list[dict]:
        rows = self.session.execute(
            select(Product.id, Product.name)
            .join(PreUploadedProduct, PreUploadedProduct.product_id == Product.id)
            .join(Order, Order.id == PreUploadedProduct.used_by_order_id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                PreUploadedProduct.is_used.is_(True),
            )
            .distinct()
            .order_by(Product.name)
        ).all()
        return [{"id": r[0], "name": r[1]} for r in rows]

    def get_exportable_variations(self, user_id: int, product_id: str) -> list[dict]:
        rows = self.session.execute(
            select(ProductVariation.id, ProductVariation.name)
            .join(PreUploadedProduct,
                  PreUploadedProduct.variation_id == ProductVariation.id)
            .join(Order, Order.id == PreUploadedProduct.used_by_order_id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                PreUploadedProduct.product_id == product_id,
                PreUploadedProduct.is_used.is_(True),
            )
            .distinct()
            .order_by(ProductVariation.name)
        ).all()
        return [{"id": r[0], "name": r[1]} for r in rows]

    def get_variant_export(
        self, user_id: int, product_id: str, variation_id: str
    ) -> ExportVariantData | None:
        product = self.session.get(Product, product_id)
        variation = self.session.get(ProductVariation, variation_id)
        if product is None or variation is None:
            return None

        rows = self.session.execute(
            select(PreUploadedProduct, Order)
            .join(Order, Order.id == PreUploadedProduct.used_by_order_id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                PreUploadedProduct.product_id == product_id,
                PreUploadedProduct.variation_id == variation_id,
                PreUploadedProduct.is_used.is_(True),
            )
            .order_by(Order.created_at, PreUploadedProduct.used_at)
        ).all()
        if not rows:
            return None

        by_order: dict[str, ExportOrderEntry] = {}
        for pre, order in rows:
            entry = by_order.get(order.id)
            if entry is None:
                item = self.session.execute(
                    select(OrderItem).where(
                        OrderItem.order_id == order.id,
                        OrderItem.product_id == product_id,
                        OrderItem.variation_id == variation_id,
                    )
                ).scalars().first()
                entry = ExportOrderEntry(
                    order_id=order.id,
                    created_at=order.created_at,
                    price=item.subtotal if item else 0,
                    quantity=item.quantity if item else 0,
                    bonus_quantity=item.bonus_quantity if item else 0,
                    contents=[],
                )
                by_order[order.id] = entry
            entry.contents.append(_render_delivery_content(pre.product_data))

        return ExportVariantData(
            product_id=product_id,
            product_name=product.name,
            variation_id=variation_id,
            variation_name=variation.name,
            orders=list(by_order.values()),
        )
