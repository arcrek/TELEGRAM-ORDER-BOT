"""
Product service layer for business logic.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.database.models import Product, DeliveryType


class ProductService:
    """Service for product operations."""

    def __init__(self, session: Session):
        """
        Initialize product service.
        
        Args:
            session: Database session
        """
        self.session = session

    def create_product(self, product_data: dict) -> Product:
        """
        Create a new product.
        
        Args:
            product_data: Dictionary with product fields
        
        Returns:
            Created Product instance
        """
        product = Product(
            id=product_data["id"],
            name=product_data["name"],
            description=product_data.get("description"),
            delivery_type=product_data.get("delivery_type", DeliveryType.PRE_UPLOADED),
            is_active=product_data.get("is_active", True),
        )
        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Get product by ID.
        
        Args:
            product_id: Product ID
        
        Returns:
            Product instance or None if not found
        """
        return self.session.query(Product).filter_by(id=product_id).first()

    def list_products(
        self,
        page: int = 1,
        per_page: int = 15,
        only_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> List[Product]:
        """
        List products with pagination, search, and sorting.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            only_active: Only return active products (None = all)
            search: Search term for name or description
            sort_by: Field to sort by (name, created_at)
            sort_order: Sort order (asc, desc)
        
        Returns:
            List of Product instances
        """
        from sqlalchemy import or_
        
        query = self.session.query(Product)
        
        # Apply search filter
        if search:
            search_lower = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    Product.name.ilike(search_lower),
                    Product.description.ilike(search_lower)
                )
            )
        
        # Apply active filter
        if only_active is not None:
            query = query.filter_by(is_active=only_active)
        
        # Apply sorting
        if sort_by == "name":
            if sort_order == "desc":
                query = query.order_by(Product.name.desc())
            else:
                query = query.order_by(Product.name.asc())
        elif sort_by == "created_at":
            if sort_order == "desc":
                query = query.order_by(Product.created_at.desc())
            else:
                query = query.order_by(Product.created_at.asc())
        else:
            # Default sort by name
            query = query.order_by(Product.name.asc())
        
        # Apply pagination
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page).all()

    def get_total_count(
        self,
        only_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> int:
        """
        Get total count of products.
        
        Args:
            only_active: Only count active products (None = all)
            search: Search term for name or description
        
        Returns:
            Total count
        """
        from sqlalchemy import or_
        
        query = self.session.query(func.count(Product.id))
        
        # Apply search filter
        if search:
            search_lower = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    Product.name.ilike(search_lower),
                    Product.description.ilike(search_lower)
                )
            )
        
        # Apply active filter
        if only_active is not None:
            query = query.filter_by(is_active=only_active)
        
        return query.scalar() or 0

    def update_product(self, product_id: str, update_data: dict) -> Optional[Product]:
        """
        Update a product.
        
        Args:
            product_id: Product ID
            update_data: Dictionary with fields to update
        
        Returns:
            Updated Product instance or None if not found
        """
        product = self.get_product_by_id(product_id)
        if not product:
            return None
        
        if "name" in update_data:
            product.name = update_data["name"]
        if "description" in update_data:
            product.description = update_data["description"]
        if "delivery_type" in update_data:
            product.delivery_type = update_data["delivery_type"]
        if "is_active" in update_data:
            product.is_active = update_data["is_active"]
        
        self.session.commit()
        self.session.refresh(product)
        return product

    def delete_product(self, product_id: str) -> bool:
        """
        Permanently delete a product from the database.
        
        Args:
            product_id: Product ID
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            ValueError: If product has related records that prevent deletion
        """
        from src.database.models import OrderItem, PreUploadedProduct
        
        product = self.get_product_by_id(product_id)
        if not product:
            return False
        
        from src.database.models import ProductVariation
        
        # Set order_items.product_id to NULL for all related order items
        # This preserves order history while allowing product deletion
        self.session.query(OrderItem).filter_by(product_id=product_id).update({"product_id": None})
        
        # Set order_items.variation_id to NULL for all variations' order items
        variations = self.session.query(ProductVariation).filter_by(product_id=product_id).all()
        for variation in variations:
            self.session.query(OrderItem).filter_by(variation_id=variation.id).update({"variation_id": None})
        
        # Delete pre-uploaded products (these can be safely deleted)
        self.session.query(PreUploadedProduct).filter_by(product_id=product_id).delete()
        
        # Variations will be deleted automatically due to cascade="all, delete-orphan"
        self.session.delete(product)
        self.session.commit()
        return True

