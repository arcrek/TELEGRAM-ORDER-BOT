"""
Pre-uploaded product service layer.
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
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
        Get an available pre-uploaded product for a variation.
        
        Args:
            variation_id: Variation ID
            quantity: Number of products needed
            
        Returns:
            PreUploadedProduct instance or None if not available
        """
        # Get first available unused product
        product = (
            self.session.query(PreUploadedProduct)
            .filter_by(variation_id=variation_id, is_used=False)
            .first()
        )
        return product

    def get_available_products(
        self, variation_id: str, quantity: int = 1
    ) -> list[PreUploadedProduct]:
        """
        Get available pre-uploaded products for a variation.
        
        Args:
            variation_id: Variation ID
            quantity: Number of products needed
            
        Returns:
            List of PreUploadedProduct instances
        """
        products = (
            self.session.query(PreUploadedProduct)
            .filter_by(variation_id=variation_id, is_used=False)
            .limit(quantity)
            .all()
        )
        return products

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
        logger.info(f"Product {product.id} raw product_data: {raw_data[:200] if len(raw_data) > 200 else raw_data}")
        
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
                failed_items.append({
                    "variation_id": None,
                    "reason": "Variation was deleted, cannot deliver pre-uploaded products"
                })
                continue
            
            # Calculate total items to deliver (quantity + bonus)
            total_items = item.quantity + (item.bonus_quantity or 0)
            
            # Get available products for this variation
            products = self.get_available_products(item.variation_id, total_items)
            
            if len(products) < total_items:
                failed_items.append({
                    "variation_id": item.variation_id,
                    "reason": f"Insufficient pre-uploaded products. Available: {len(products)}, Required: {total_items} (quantity: {item.quantity} + bonus: {item.bonus_quantity or 0})"
                })
                continue
            
            # Mark products as used and collect data
            for product in products:
                marked = self.mark_product_as_used(product.id, order_id)
                if marked:
                    product_data = self.get_product_data(marked)
                    delivered_products.append({
                        "id": marked.id,
                        "variation_id": item.variation_id,
                        "data": product_data
                    })
        
        success = len(failed_items) == 0

        return {
            "success": success,
            "products": delivered_products,
            "failed_items": failed_items
        }

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
                # Total available
                in_stock: int = (
                    self.session.query(PreUploadedProduct)
                    .filter_by(variation_id=variant.id, is_used=False)
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
                    cutoff_expiring = now + relativedelta(days=EXPIRING_SOON_DAYS) - delta

                    # Naive comparison: strip timezone awareness for SQLite compatibility
                    cutoff_aging_naive = cutoff_aging.replace(tzinfo=None)
                    cutoff_expiring_naive = cutoff_expiring.replace(tzinfo=None)

                    aging = (
                        self.session.query(PreUploadedProduct)
                        .filter(
                            PreUploadedProduct.variation_id == variant.id,
                            PreUploadedProduct.is_used.is_(False),
                            PreUploadedProduct.created_at <= cutoff_aging_naive,
                        )
                        .count()
                    )

                    expiring_soon = (
                        self.session.query(PreUploadedProduct)
                        .filter(
                            PreUploadedProduct.variation_id == variant.id,
                            PreUploadedProduct.is_used.is_(False),
                            PreUploadedProduct.created_at > cutoff_aging_naive,
                            PreUploadedProduct.created_at <= cutoff_expiring_naive,
                        )
                        .count()
                    )

                variant_stats.append({
                    "variation_id": variant.id,
                    "variation_name": variant.name,
                    "in_stock": in_stock,
                    "aging": aging,
                    "expiring_soon": expiring_soon,
                    "threshold_value": tv,
                    "threshold_unit": tu,
                })

            result.append({
                "product_id": product.id,
                "product_name": product.name,
                "variants": variant_stats,
            })

        return result

