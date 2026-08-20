"""
Supplier service layer.
"""
import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.database.models.enums import SupplierOrderStatus
from src.database.models.supplier import Supplier
from src.database.models.supplier_order import SupplierOrder


class SupplierService:
    """Service for supplier operations."""

    def __init__(self, session: Session):
        """
        Initialize supplier service.
        
        Args:
            session: Database session
        """
        self.session = session

    def generate_supplier_id(self) -> str:
        """
        Generate a unique supplier ID.
        
        Returns:
            Supplier ID string
        """
        return f"supp_{uuid.uuid4().hex[:8]}"

    def get_supplier_by_telegram_id(
        self, telegram_user_id: int
    ) -> Supplier | None:
        """
        Get supplier by Telegram user ID.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            Supplier instance or None if not found
        """
        return (
            self.session.query(Supplier)
            .filter_by(telegram_user_id=telegram_user_id)
            .first()
        )

    def get_supplier_by_id(self, supplier_id: str) -> Supplier | None:
        """
        Get supplier by ID.
        
        Args:
            supplier_id: Supplier ID
            
        Returns:
            Supplier instance or None if not found
        """
        return self.session.query(Supplier).filter_by(id=supplier_id).first()

    def create_supplier(
        self, telegram_user_id: int, name: str, is_active: bool = True
    ) -> Supplier | None:
        """
        Create a new supplier.
        
        Args:
            telegram_user_id: Telegram user ID
            name: Supplier name
            is_active: Whether supplier is active (default: True)
            
        Returns:
            Created Supplier instance or None if creation failed
        """
        # Check if supplier already exists
        existing = self.get_supplier_by_telegram_id(telegram_user_id)
        if existing:
            return None  # Supplier already exists
        
        supplier = Supplier(
            id=self.generate_supplier_id(),
            telegram_user_id=telegram_user_id,
            name=name,
            is_active=is_active,
        )
        
        self.session.add(supplier)
        self.session.commit()
        self.session.refresh(supplier)
        
        return supplier

    def update_supplier_status(
        self, supplier_id: str, is_active: bool
    ) -> Supplier | None:
        """
        Update supplier active status.
        
        Args:
            supplier_id: Supplier ID
            is_active: New active status
            
        Returns:
            Updated Supplier instance or None if not found
        """
        supplier = self.get_supplier_by_id(supplier_id)
        if not supplier:
            return None
        
        supplier.is_active = is_active
        self.session.commit()
        self.session.refresh(supplier)
        
        return supplier

    def is_supplier_registered(self, telegram_user_id: int) -> bool:
        """
        Check if a Telegram user is registered as a supplier.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            True if registered, False otherwise
        """
        supplier = self.get_supplier_by_telegram_id(telegram_user_id)
        return supplier is not None and supplier.is_active

    def list_suppliers(
        self,
        only_active: bool | None = None,
        limit: int = 100,
    ) -> list[Supplier]:
        """
        List all suppliers with optional filtering.
        
        Args:
            only_active: Filter by active status (None = all)
            limit: Maximum number of suppliers to return
            
        Returns:
            List of Supplier instances
        """
        query = self.session.query(Supplier)
        
        if only_active is not None:
            query = query.filter_by(is_active=only_active)
        
        return query.order_by(desc(Supplier.created_at)).limit(limit).all()

    def get_supplier_order_history(
        self,
        supplier_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get order history for a supplier.
        
        Args:
            supplier_id: Supplier ID
            limit: Maximum number of orders to return
            
        Returns:
            List of dictionaries with order information
        """
        supplier_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id)
            .order_by(desc(SupplierOrder.created_at))
            .limit(limit)
            .all()
        )
        
        results = []
        for supplier_order in supplier_orders:
            order = supplier_order.order
            if order:
                results.append({
                    "supplier_order_id": supplier_order.id,
                    "order_id": order.id,
                    "status": supplier_order.status.value,
                    "order_status": order.status.value,
                    "total_amount": order.total_amount,
                    "created_at": supplier_order.created_at.isoformat(),
                    "updated_at": supplier_order.updated_at.isoformat(),
                })
        
        return results

    def get_supplier_statistics(self, supplier_id: str) -> dict:
        """
        Get performance statistics for a supplier.
        
        Args:
            supplier_id: Supplier ID
            
        Returns:
            Dictionary with statistics
        """
        supplier = self.get_supplier_by_id(supplier_id)
        if not supplier:
            return {}
        
        # Count orders by status
        total_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id)
            .count()
        )
        
        pending_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id, status=SupplierOrderStatus.PENDING)
            .count()
        )
        
        in_progress_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id, status=SupplierOrderStatus.IN_PROGRESS)
            .count()
        )
        
        delivered_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id, status=SupplierOrderStatus.DELIVERED)
            .count()
        )
        
        cancelled_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id, status=SupplierOrderStatus.CANCELLED)
            .count()
        )
        
        # Calculate total revenue from delivered orders
        delivered_supplier_orders = (
            self.session.query(SupplierOrder)
            .filter_by(supplier_id=supplier_id, status=SupplierOrderStatus.DELIVERED)
            .all()
        )
        
        total_revenue = sum(
            so.order.total_amount for so in delivered_supplier_orders
            if so.order
        )
        
        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier.name,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "in_progress_orders": in_progress_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "total_revenue": total_revenue,
        }

