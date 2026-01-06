"""
Supplier order service layer.
"""
import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from src.database.models.supplier_order import SupplierOrder
from src.database.models.order import Order
from src.database.models.product import Product
from src.database.models.supplier import Supplier
from src.database.models.enums import SupplierOrderStatus


class SupplierOrderService:
    """Service for supplier order operations."""

    def __init__(self, session: Session):
        """
        Initialize supplier order service.
        
        Args:
            session: Database session
        """
        self.session = session

    def generate_supplier_order_id(self) -> str:
        """
        Generate a unique supplier order ID.
        
        Returns:
            Supplier order ID string
        """
        return f"supp_{uuid.uuid4().hex[:8]}"

    def get_supplier_for_product(self, product_id: str) -> Optional[Supplier]:
        """
        Get the supplier for a product.
        First tries to get primary supplier from assignments, then falls back to first active supplier.
        
        Args:
            product_id: Product ID
            
        Returns:
            Supplier instance or None if not found
        """
        # Try to get primary supplier from assignments
        from src.database.services.product_supplier_assignment_service import ProductSupplierAssignmentService
        assignment_service = ProductSupplierAssignmentService(self.session)
        primary_supplier = assignment_service.get_primary_supplier_for_product(product_id)
        
        if primary_supplier and primary_supplier.is_active:
            return primary_supplier
        
        # Fall back to first active supplier if no primary assignment
        supplier = (
            self.session.query(Supplier)
            .filter_by(is_active=True)
            .first()
        )
        return supplier

    def create_supplier_order(
        self, order_id: str, supplier_id: str
    ) -> Optional[SupplierOrder]:
        """
        Create a supplier order record.
        
        Args:
            order_id: Order ID
            supplier_id: Supplier ID
            
        Returns:
            Created SupplierOrder instance or None if creation failed
        """
        # Check if supplier order already exists
        existing = (
            self.session.query(SupplierOrder)
            .filter_by(order_id=order_id, supplier_id=supplier_id)
            .first()
        )
        if existing:
            return existing
        
        supplier_order = SupplierOrder(
            id=self.generate_supplier_order_id(),
            order_id=order_id,
            supplier_id=supplier_id,
            status=SupplierOrderStatus.PENDING,
        )
        
        self.session.add(supplier_order)
        self.session.commit()
        self.session.refresh(supplier_order)
        
        return supplier_order

    def create_supplier_orders_for_order(self, order_id: str) -> List[SupplierOrder]:
        """
        Create supplier orders for all items in an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            List of created SupplierOrder instances
        """
        order = self.session.query(Order).filter_by(id=order_id).first()
        if not order:
            return []
        
        supplier_orders = []
        
        # Group items by product (and thus by supplier)
        products_processed = set()
        
        for item in order.items:
            product_id = item.product_id
            if not product_id or product_id in products_processed:
                continue  # Skip if product was deleted or already processed
            
            # Get supplier for this product
            supplier = self.get_supplier_for_product(product_id)
            if not supplier:
                continue
            
            # Create supplier order
            supplier_order = self.create_supplier_order(order_id, supplier.id)
            if supplier_order:
                supplier_orders.append(supplier_order)
                products_processed.add(product_id)
        
        return supplier_orders

    def format_order_notification(self, order_id: str) -> Optional[str]:
        """
        Format order notification message for supplier.
        
        Args:
            order_id: Order ID
            
        Returns:
            Formatted message string or None if order not found
        """
        order = self.session.query(Order).filter_by(id=order_id).first()
        if not order:
            return None
        
        lines = [
            "📦 NEW ORDER",
            f"Order ID: {order.id}",
            f"User ID: {order.user_id}",
            f"Total: {order.total_amount:,} VND",
            "",
            "Items:"
        ]
        
        for item in order.items:
            if not item.product_id or not item.variation_id:
                # Product or variation was deleted, show placeholder
                lines.append(
                    f"  • [Deleted Product/Variation] x{item.quantity}"
                )
                continue
            product = self.session.query(Product).filter_by(id=item.product_id).first()
            variation = item.variation
            if product and variation:
                lines.append(
                    f"  • {product.name} - {variation.name} x{item.quantity}"
                )
            else:
                # Product or variation not found (shouldn't happen, but handle gracefully)
                lines.append(
                    f"  • [Unknown Product/Variation] x{item.quantity}"
                )
        
        return "\n".join(lines)

    def update_notification_message_id(
        self, supplier_order_id: str, message_id: int
    ) -> Optional[SupplierOrder]:
        """
        Update the notification message ID for a supplier order.
        
        Args:
            supplier_order_id: Supplier order ID
            message_id: Telegram message ID
            
        Returns:
            Updated SupplierOrder instance or None if not found
        """
        supplier_order = (
            self.session.query(SupplierOrder)
            .filter_by(id=supplier_order_id)
            .first()
        )
        if not supplier_order:
            return None
        
        supplier_order.notification_message_id = message_id
        self.session.commit()
        self.session.refresh(supplier_order)
        
        return supplier_order

    def get_supplier_order_by_id(
        self, supplier_order_id: str
    ) -> Optional[SupplierOrder]:
        """
        Get supplier order by ID.
        
        Args:
            supplier_order_id: Supplier order ID
            
        Returns:
            SupplierOrder instance or None if not found
        """
        return (
            self.session.query(SupplierOrder)
            .filter_by(id=supplier_order_id)
            .first()
        )

