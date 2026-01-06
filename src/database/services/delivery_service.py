"""
Delivery service layer for handling order fulfillment.
"""
from typing import Optional
from sqlalchemy.orm import Session
from src.database.models.product import Product
from src.database.models.enums import OrderStatus, DeliveryType
from src.database.services.order_service import OrderService


class DeliveryService:
    """Service for delivery operations."""

    def __init__(self, session: Session):
        """
        Initialize delivery service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.order_service = OrderService(session)

    def get_order_delivery_type(self, order_id: str) -> Optional[DeliveryType]:
        """
        Get the delivery type for an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            DeliveryType or None if order not found
        """
        order = self.order_service.get_order_by_id(order_id)
        if not order or not order.items:
            return None
        
        # Get the first order item's product
        order_item = order.items[0]
        if not order_item.product_id:
            return None  # Product was deleted, cannot determine delivery type
        product = self.session.query(Product).filter_by(id=order_item.product_id).first()
        if not product:
            return None
        
        return product.delivery_type

    def process_paid_order(self, order_id: str) -> bool:
        """
        Process an order after payment confirmation.
        Determines delivery type and triggers appropriate delivery process.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if processing started successfully, False otherwise
        """
        order = self.order_service.get_order_by_id(order_id)
        if not order:
            return False
        
        # Get delivery type
        delivery_type = self.get_order_delivery_type(order_id)
        if not delivery_type:
            return False
        
        # Update order status to PROCESSING
        self.order_service.update_order_status(order_id, OrderStatus.PROCESSING)
        
        # Decrease stock for all order items
        for item in order.items:
            if not item.variation_id:
                continue  # Variation was deleted, skip stock decrease
            try:
                self.order_service.decrease_stock(item.variation_id, item.quantity)
            except ValueError:
                # Log error but continue processing
                # In production, you might want to handle this differently
                pass
        
        return True

