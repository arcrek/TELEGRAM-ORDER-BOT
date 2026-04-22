"""
Product variation service layer for business logic.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from src.database.models import ProductVariation
from src.database.models.enums import DeliveryType


class VariationService:
    """Service for product variation operations."""

    def __init__(self, session: Session):
        """
        Initialize variation service.
        
        Args:
            session: Database session
        """
        self.session = session

    def create_variation(self, variation_data: dict) -> ProductVariation:
        """
        Create a new product variation.
        
        Args:
            variation_data: Dictionary with variation fields
        
        Returns:
            Created ProductVariation instance
        """
        variation = ProductVariation(
            id=variation_data["id"],
            product_id=variation_data["product_id"],
            name=variation_data["name"],
            price=variation_data["price"],
            stock=variation_data.get("stock", 0),
            is_active=variation_data.get("is_active", True),
        )
        self.session.add(variation)
        self.session.commit()
        self.session.refresh(variation)
        return variation

    def get_variation_by_id(self, variation_id: str) -> Optional[ProductVariation]:
        """
        Get variation by ID.
        
        Args:
            variation_id: Variation ID
        
        Returns:
            ProductVariation instance or None if not found
        """
        return self.session.query(ProductVariation).filter_by(id=variation_id).first()

    def list_variations_by_product(
        self,
        product_id: str,
        only_active: bool = True,
    ) -> List[ProductVariation]:
        """
        List variations for a product.
        
        Args:
            product_id: Product ID
            only_active: Only return active variations
        
        Returns:
            List of ProductVariation instances
        """
        query = self.session.query(ProductVariation).filter_by(product_id=product_id)
        
        if only_active:
            query = query.filter_by(is_active=True)
        
        return query.order_by(ProductVariation.name).all()

    def update_variation(
        self,
        variation_id: str,
        update_data: dict,
    ) -> Optional[ProductVariation]:
        """
        Update a variation.
        
        Args:
            variation_id: Variation ID
            update_data: Dictionary with fields to update
        
        Returns:
            Updated ProductVariation instance or None if not found
        """
        variation = self.get_variation_by_id(variation_id)
        if not variation:
            return None
        
        if "name" in update_data:
            variation.name = update_data["name"]
        if "price" in update_data:
            variation.price = update_data["price"]
        if "stock" in update_data:
            variation.stock = update_data["stock"]
        if "is_active" in update_data:
            variation.is_active = update_data["is_active"]
        if "benefit_mode" in update_data:
            variation.benefit_mode = update_data["benefit_mode"]
        
        self.session.commit()
        self.session.refresh(variation)
        return variation

    def update_stock(self, variation_id: str, new_stock: int) -> Optional[ProductVariation]:
        """
        Update stock for a variation.
        
        Args:
            variation_id: Variation ID
            new_stock: New stock value
        
        Returns:
            Updated ProductVariation instance or None if not found
        """
        return self.update_variation(variation_id, {"stock": new_stock})

    def decrease_stock(self, variation_id: str, quantity: int) -> Optional[ProductVariation]:
        """
        Decrease stock for a variation (used when order is placed).
        For PRE_UPLOADED products: validates availability from pre-uploaded products.
        For SUPPLIER_BASED products: decreases the stock field directly.
        
        Args:
            variation_id: Variation ID
            quantity: Quantity to decrease
        
        Returns:
            ProductVariation instance or None if not found
        
        Raises:
            ValueError: If insufficient stock
        """
        variation = self.get_variation_by_id(variation_id)
        if not variation:
            return None
        
        # Get product to check delivery type
        from src.database.services.product_service import ProductService
        product_service = ProductService(self.session)
        product = product_service.get_product_by_id(variation.product_id)
        
        if not product:
            raise ValueError(f"Product {variation.product_id} not found")
        
        if product.delivery_type == DeliveryType.PRE_UPLOADED:
            # For PRE_UPLOADED products, validate from pre-uploaded products
            available_stock = self.calculate_stock_from_pre_uploaded(variation_id)
            if available_stock < quantity:
                raise ValueError(f"Insufficient stock. Available: {available_stock}, Requested: {quantity}")
            # Stock is managed through pre-uploaded products, so we don't modify variation.stock
            # The actual reduction happens when pre-uploaded products are marked as used
        else:
            # For SUPPLIER_BASED products, decrease the stock field directly
            if variation.stock < quantity:
                raise ValueError(f"Insufficient stock. Available: {variation.stock}, Requested: {quantity}")
            variation.stock -= quantity
            self.session.commit()
            self.session.refresh(variation)
        
        return variation

    def delete_variation(self, variation_id: str) -> bool:
        """
        Permanently delete a variation from the database.
        
        Args:
            variation_id: Variation ID
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            ValueError: If variation has related records that prevent deletion
        """
        from src.database.models import OrderItem, PreUploadedProduct
        
        variation = self.get_variation_by_id(variation_id)
        if not variation:
            return False
        
        # Set order_items.variation_id to NULL for all related order items
        # This preserves order history while allowing variation deletion
        self.session.query(OrderItem).filter_by(variation_id=variation_id).update({"variation_id": None})
        
        # Delete pre-uploaded products (these can be safely deleted)
        self.session.query(PreUploadedProduct).filter_by(variation_id=variation_id).delete()
        
        self.session.delete(variation)
        self.session.commit()
        return True

    def list_all_variations_grouped(
        self,
        product_id: Optional[str] = None,
        only_active: Optional[bool] = None,
    ) -> List[dict]:
        """
        List all variations grouped by product.
        
        Args:
            product_id: Optional product ID to filter by
            only_active: Optional filter for active variations only
        
        Returns:
            List of dictionaries with product info and variations
        """
        from src.database.models import Product
        
        # Query variations
        query = self.session.query(ProductVariation)
        
        if product_id:
            query = query.filter_by(product_id=product_id)
        if only_active is not None:
            query = query.filter_by(is_active=only_active)
        
        variations = query.order_by(ProductVariation.product_id, ProductVariation.name).all()
        
        # Group by product
        grouped = {}
        for variation in variations:
            if variation.product_id not in grouped:
                product = self.session.query(Product).filter_by(id=variation.product_id).first()
                grouped[variation.product_id] = {
                    "product_id": variation.product_id,
                    "product_name": product.name if product else "Unknown",
                    "variations": [],
                }
            
            # Calculate stock from pre-uploaded products
            calculated_stock = self.calculate_stock_from_pre_uploaded(variation.id)
            
            grouped[variation.product_id]["variations"].append({
                "id": variation.id,
                "name": variation.name,
                "price": variation.price,
                "stock": calculated_stock,
                "is_active": variation.is_active,
                "created_at": variation.created_at.isoformat(),
                "updated_at": variation.updated_at.isoformat(),
            })
        
        return list(grouped.values())

    def calculate_stock_from_pre_uploaded(self, variation_id: str) -> int:
        """
        Calculate stock from available pre-uploaded products.
        
        Args:
            variation_id: Variation ID
        
        Returns:
            Count of available (not used) pre-uploaded products
        """
        from src.database.models import PreUploadedProduct
        
        count = self.session.query(PreUploadedProduct).filter_by(
            variation_id=variation_id,
            is_used=False
        ).count()
        
        return count

    def get_low_stock_variations(
        self,
        threshold: int = 5,
    ) -> List[dict]:
        """
        Get variations with stock below threshold, grouped by product.
        
        Args:
            threshold: Stock threshold (default: 5)
        
        Returns:
            List of dictionaries with product info and low stock variations
        """
        from src.database.models import Product
        
        # Get all variations and calculate stock for each
        variations = self.session.query(ProductVariation).order_by(
            ProductVariation.product_id, ProductVariation.name
        ).all()
        
        # Group by product and filter by calculated stock
        grouped = {}
        for variation in variations:
            # Calculate stock from pre-uploaded products
            calculated_stock = self.calculate_stock_from_pre_uploaded(variation.id)
            
            # Only include if stock is below threshold
            if calculated_stock > threshold:
                continue
            
            if variation.product_id not in grouped:
                product = self.session.query(Product).filter_by(id=variation.product_id).first()
                grouped[variation.product_id] = {
                    "product_id": variation.product_id,
                    "product_name": product.name if product else "Unknown",
                    "variations": [],
                }
            
            grouped[variation.product_id]["variations"].append({
                "id": variation.id,
                "name": variation.name,
                "price": variation.price,
                "stock": calculated_stock,
                "is_active": variation.is_active,
                "created_at": variation.created_at.isoformat(),
                "updated_at": variation.updated_at.isoformat(),
            })
        
        return list(grouped.values())

