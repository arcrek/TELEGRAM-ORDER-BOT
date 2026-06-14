"""
Pre-uploaded product service layer.
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy import text, or_
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.order import Order

# Number of days ahead to consider a record "expiring soon"
EXPIRING_SOON_DAYS = 3


class PreUploadedService:
    """Service for pre-uploaded product operations."""

    def __init__(self, session: Session):
        """
        Initialize pre-uploaded service.

        Args:
            session: Database session
        """
        self.session = session

    def get_available_product(
        self, variation_id: str, quantity: int = 1
    ) -> Optional[PreUploadedProduct]:
        """
        Get an available (unreserved) pre-uploaded product for a variation.
        """
        product = (
            self.session.query(PreUploadedProduct)
            .filter(
                PreUploadedProduct.variation_id == variation_id,
                PreUploadedProduct.is_used.is_(False),
                PreUploadedProduct.reserved_by_order_id.is_(None),
            )
            .first()
        )
        return product

    def get_available_products(
        self, variation_id: str, quantity: int = 1
    ) -> list[PreUploadedProduct]:
        """
        Get unreserved available pre-uploaded products for a variation.
        Used for stock display; does NOT include reserved rows.
        """
        products = (
            self.session.query(PreUploadedProduct)
            .filter(
                PreUploadedProduct.variation_id == variation_id,
                PreUploadedProduct.is_used.is_(False),
                PreUploadedProduct.reserved_by_order_id.is_(None),
            )
            .limit(quantity)
            .all()
        )
        return products

    def get_in_stock_product_ids(self, product_ids: List[str]) -> set[str]:
        """
        Return the subset of product_ids that have at least one available
        (is_used=False, unreserved) pre-uploaded item across any of their variations.
        Single aggregate query — safe to call for the full product list.
        """
        from src.database.models.product_variation import ProductVariation

        if not product_ids:
            return set()

        rows = (
            self.session.query(ProductVariation.product_id)
            .join(
                PreUploadedProduct,
                PreUploadedProduct.variation_id == ProductVariation.id,
            )
            .filter(
                ProductVariation.product_id.in_(product_ids),
                PreUploadedProduct.is_used.is_(False),
                PreUploadedProduct.reserved_by_order_id.is_(None),
            )
            .distinct()
            .all()
        )
        return {row.product_id for row in rows}

    def reserve_products_for_order(
        self, order_id: str, variation_id: str, quantity: int
    ) -> int:
        """
        Atomically reserve `quantity` pre-uploaded products for an order.

        Uses FOR UPDATE SKIP LOCKED so concurrent calls never claim the same rows.
        Must be called inside the same transaction as Order creation — the caller
        commits (or rolls back on failure).

        Returns the number of rows actually reserved (< quantity means stock ran out).
        """
        result = self.session.execute(
            text("""
                UPDATE pre_uploaded_products
                SET reserved_by_order_id = :order_id,
                    reserved_at = NOW()
                WHERE id IN (
                    SELECT id FROM pre_uploaded_products
                    WHERE variation_id = :variation_id
                      AND is_used = FALSE
                      AND reserved_by_order_id IS NULL
                    ORDER BY created_at
                    LIMIT :quantity
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id
            """),
            {"order_id": order_id, "variation_id": variation_id, "quantity": quantity},
        )
        return len(result.fetchall())

    def release_reservations_for_order(self, order_id: str) -> int:
        """
        Release all product reservations held by an order (called on cancellation).
        Returns the number of rows released.
        """
        result = self.session.execute(
            text("""
                UPDATE pre_uploaded_products
                SET reserved_by_order_id = NULL,
                    reserved_at = NULL
                WHERE reserved_by_order_id = :order_id
                  AND is_used = FALSE
            """),
            {"order_id": order_id},
        )
        return result.rowcount

    def _get_products_for_delivery(
        self, variation_id: str, order_id: str, quantity: int
    ) -> list[PreUploadedProduct]:
        """
        Get products to deliver for a specific order.

        Prioritises rows reserved for this order (guaranteed allocation), then
        falls back to any unreserved rows. The fallback covers orders that were
        created before the reservation feature was deployed.
        """
        from sqlalchemy import case as sa_case

        return (
            self.session.query(PreUploadedProduct)
            .filter(
                PreUploadedProduct.variation_id == variation_id,
                PreUploadedProduct.is_used.is_(False),
                or_(
                    PreUploadedProduct.reserved_by_order_id == order_id,
                    PreUploadedProduct.reserved_by_order_id.is_(None),
                ),
            )
            .order_by(
                sa_case(
                    (PreUploadedProduct.reserved_by_order_id == order_id, 0),
                    else_=1,
                ),
                PreUploadedProduct.created_at,
            )
            .limit(quantity)
            .all()
        )

    def mark_product_as_used(
        self, product_id: str, order_id: str
    ) -> Optional[PreUploadedProduct]:
        """
        Mark a pre-uploaded product as used.

        Args:
            product_id: Pre-uploaded product ID
            order_id: Order ID that used this product

        Returns:
            Updated PreUploadedProduct instance or None if not found
        """
        product = (
            self.session.query(PreUploadedProduct)
            .filter_by(id=product_id, is_used=False)
            .first()
        )
        if not product:
            return None

        product.is_used = True
        product.used_by_order_id = order_id
        product.used_at = datetime.now(timezone.utc)
        product.reserved_by_order_id = None
        product.reserved_at = None

        self.session.commit()
        self.session.refresh(product)
        return product

    def get_product_data(self, product: PreUploadedProduct) -> Dict[str, Any]:
        """
        Parse product data from JSON string or plain text.

        Args:
            product: PreUploadedProduct instance

        Returns:
            Parsed product data as dictionary
        """
        import logging

        logger = logging.getLogger(__name__)

        if not product.product_data:
            logger.warning(f"Product {product.id} has no product_data (None or empty)")
            return {}

        raw_data = product.product_data
        logger.info(
            f"Product {product.id} raw product_data: {raw_data[:200] if len(raw_data) > 200 else raw_data}"
        )

        # Try to parse as JSON first
        try:
            parsed = json.loads(raw_data)
            if isinstance(parsed, dict):
                return parsed
            else:
                # JSON but not a dict (e.g., a string like "account@email.com")
                return {"value": parsed}
        except (json.JSONDecodeError, TypeError):
            # Not valid JSON - treat as plain text
            logger.info(f"Product {product.id} product_data is plain text, not JSON")
            # Return as a dict with the raw text
            return {"delivery_data": raw_data}

    def deliver_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Deliver pre-uploaded products for an order.

        Args:
            order_id: Order ID

        Returns:
            Dictionary with delivery data or None if delivery failed
            Format: {
                "success": bool,
                "products": [{"id": str, "data": dict}, ...],
                "failed_items": [{"variation_id": str, "reason": str}, ...]
            }
        """
        order = self.session.query(Order).filter_by(id=order_id).first()
        if not order:
            return None

        delivered_products = []
        failed_items = []

        for item in order.items:
            if not item.variation_id:
                # Variation was deleted, cannot deliver
                failed_items.append(
                    {
                        "variation_id": None,
                        "reason": "Variation was deleted, cannot deliver pre-uploaded products",
                    }
                )
                continue

            # Calculate total items to deliver (quantity + bonus)
            total_items = item.quantity + (item.bonus_quantity or 0)

            # Get products reserved for this order (or unreserved fallback for
            # orders created before the reservation feature was deployed)
            products = self._get_products_for_delivery(
                item.variation_id, order_id, total_items
            )

            if len(products) < total_items:
                failed_items.append(
                    {
                        "variation_id": item.variation_id,
                        "reason": f"Insufficient pre-uploaded products. Available: {len(products)}, Required: {total_items} (quantity: {item.quantity} + bonus: {item.bonus_quantity or 0})",
                    }
                )
                continue

            # Mark products as used and collect data
            for product in products:
                marked = self.mark_product_as_used(product.id, order_id)
                if marked:
                    product_data = self.get_product_data(marked)
                    delivered_products.append(
                        {
                            "id": marked.id,
                            "variation_id": item.variation_id,
                            "data": product_data,
                        }
                    )

        success = len(failed_items) == 0

        return {
            "success": success,
            "products": delivered_products,
            "failed_items": failed_items,
        }

    def export_available_products(
        self, product_id: str, variation_id: str, amount: int
    ) -> list[PreUploadedProduct]:
        """
        Atomically claim up to `amount` available rows and mark them sold (admin export).

        Uses ORM with_for_update(skip_locked=True): on Postgres this acquires a real
        row lock so concurrent exports never claim the same rows; on SQLite (used in
        tests) the clause is silently dropped and a plain SELECT runs instead.

        Exported rows get is_used=True and used_at=now(); used_by_order_id is left NULL
        to distinguish admin-exported stock from order-fulfilled stock.

        Returns the rows actually marked (may be fewer than `amount` if stock is short).
        """
        products = (
            self.session.query(PreUploadedProduct)
            .filter(
                PreUploadedProduct.product_id == product_id,
                PreUploadedProduct.variation_id == variation_id,
                PreUploadedProduct.is_used.is_(False),
                PreUploadedProduct.reserved_by_order_id.is_(None),
            )
            .order_by(PreUploadedProduct.created_at)
            .with_for_update(skip_locked=True)
            .limit(amount)
            .all()
        )

        now = datetime.now(timezone.utc)
        for p in products:
            p.is_used = True
            p.used_at = now
            # used_by_order_id intentionally left NULL — admin export, not an order

        self.session.commit()
        return products

    def get_inventory_stats_by_product(self) -> List[Dict[str, Any]]:
        """
        Compute per-variant inventory statistics for all PRE_UPLOADED products.

        For each available (is_used=False) record:
          - in_stock: total count of available records for the variant.
          - aging: count of available records whose created_at is older than the
            variant's warning_threshold (today - threshold >= created_at).
          - expiring_soon: count of available records that will cross the threshold
            within the next EXPIRING_SOON_DAYS days.

        Variants without a configured threshold return aging=0, expiring_soon=0.

        Returns:
            List of product dicts, each containing a list of variant stat dicts.
        """
        from src.database.models.product import Product
        from src.database.models.product_variation import ProductVariation
        from src.database.models.enums import DeliveryType

        now = datetime.now(timezone.utc)

        # Fetch only PRE_UPLOADED products
        products: List[Product] = (
            self.session.query(Product)
            .filter(Product.delivery_type == DeliveryType.PRE_UPLOADED)
            .order_by(Product.name)
            .all()
        )

        result: List[Dict[str, Any]] = []

        for product in products:
            variants: List[ProductVariation] = (
                self.session.query(ProductVariation)
                .filter_by(product_id=product.id)
                .order_by(ProductVariation.name)
                .all()
            )

            variant_stats = []
            for variant in variants:
                # Total available (unreserved)
                in_stock: int = (
                    self.session.query(PreUploadedProduct)
                    .filter(
                        PreUploadedProduct.variation_id == variant.id,
                        PreUploadedProduct.is_used.is_(False),
                        PreUploadedProduct.reserved_by_order_id.is_(None),
                    )
                    .count()
                )

                aging = 0
                expiring_soon = 0

                tv = variant.warning_threshold_value
                tu = variant.warning_threshold_unit

                if tv is not None and tu is not None:
                    delta = relativedelta(**{tu: tv})  # type: ignore[arg-type]
                    # cutoff_aging: records created on or before this date are "aged"
                    cutoff_aging = now - delta
                    # cutoff_expiring: records created on or before this date will
                    # expire within the next EXPIRING_SOON_DAYS days
                    cutoff_expiring = (
                        now + relativedelta(days=EXPIRING_SOON_DAYS) - delta
                    )

                    # Naive comparison: strip timezone awareness for SQLite compatibility
                    cutoff_aging_naive = cutoff_aging.replace(tzinfo=None)
                    cutoff_expiring_naive = cutoff_expiring.replace(tzinfo=None)

                    aging = (
                        self.session.query(PreUploadedProduct)
                        .filter(
                            PreUploadedProduct.variation_id == variant.id,
                            PreUploadedProduct.is_used.is_(False),
                            PreUploadedProduct.reserved_by_order_id.is_(None),
                            PreUploadedProduct.created_at <= cutoff_aging_naive,
                        )
                        .count()
                    )

                    expiring_soon = (
                        self.session.query(PreUploadedProduct)
                        .filter(
                            PreUploadedProduct.variation_id == variant.id,
                            PreUploadedProduct.is_used.is_(False),
                            PreUploadedProduct.reserved_by_order_id.is_(None),
                            PreUploadedProduct.created_at > cutoff_aging_naive,
                            PreUploadedProduct.created_at <= cutoff_expiring_naive,
                        )
                        .count()
                    )

                variant_stats.append(
                    {
                        "variation_id": variant.id,
                        "variation_name": variant.name,
                        "in_stock": in_stock,
                        "aging": aging,
                        "expiring_soon": expiring_soon,
                        "threshold_value": tv,
                        "threshold_unit": tu,
                    }
                )

            result.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "variants": variant_stats,
                }
            )

        return result
