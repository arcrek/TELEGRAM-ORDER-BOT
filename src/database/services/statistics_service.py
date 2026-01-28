"""
Statistics service for order and sales analytics.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from src.database.models import Order, OrderItem, Product
from src.database.models.enums import OrderStatus


class StatisticsService:
    """Service for order and sales statistics."""
    
    def __init__(self, session: Session):
        """
        Initialize statistics service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    def _get_date_range(self, period: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Get date range for period filter.
        
        Args:
            period: Period string ('today', 'this_week', 'this_month', None for all time)
        
        Returns:
            Tuple of (start_date, end_date) or (None, None) for all time
        """
        now = datetime.now(timezone.utc)
        
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        elif period == "this_week":
            start = now - timedelta(days=7)
            return start, now
        elif period == "this_month":
            start = now - timedelta(days=30)
            return start, now
        else:
            return None, None
    
    def get_total_orders_count(self, period: Optional[str] = None) -> int:
        """
        Get total orders count.
        
        Args:
            period: Period filter ('today', 'this_week', 'this_month', None for all time)
        
        Returns:
            Total orders count
        """
        query = self.session.query(func.count(Order.id))
        
        if period:
            start_date, end_date = self._get_date_range(period)
            if start_date and end_date:
                query = query.filter(
                    and_(
                        Order.created_at >= start_date,
                        Order.created_at <= end_date
                    )
                )
        
        return query.scalar() or 0
    
    def get_total_revenue(self, period: Optional[str] = None) -> int:
        """
        Get total revenue (sum of paid and delivered orders).
        
        Args:
            period: Period filter ('today', 'this_week', 'this_month', None for all time)
        
        Returns:
            Total revenue in VND
        """
        query = self.session.query(func.sum(Order.total_amount)).filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED])
        )
        
        if period:
            start_date, end_date = self._get_date_range(period)
            if start_date and end_date:
                query = query.filter(
                    and_(
                        Order.created_at >= start_date,
                        Order.created_at <= end_date
                    )
                )
        
        result = query.scalar()
        return int(result) if result else 0
    
    def get_orders_by_status(self) -> Dict[str, int]:
        """
        Get orders grouped by status.
        
        Returns:
            Dictionary mapping status to count
        """
        results = (
            self.session.query(Order.status, func.count(Order.id))
            .group_by(Order.status)
            .all()
        )
        
        return {status.value: count for status, count in results}
    
    def get_orders_by_product(self) -> List[Dict[str, any]]:
        """
        Get orders grouped by product.
        
        Returns:
            List of dictionaries with product_id, product_name, and order_count
        """
        results = (
            self.session.query(
                Product.id,
                Product.name,
                func.count(OrderItem.order_id.distinct()).label('order_count')
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .group_by(Product.id, Product.name)
            .all()
        )
        
        return [
            {
                "product_id": product_id,
                "product_name": product_name,
                "order_count": order_count
            }
            for product_id, product_name, order_count in results
        ]
    
    def get_revenue_over_time(
        self,
        interval: str = "daily",
        days: int = 30
    ) -> List[Dict[str, any]]:
        """
        Get revenue over time.
        
        Args:
            interval: Time interval ('daily', 'weekly', 'monthly')
            days: Number of days to look back
        
        Returns:
            List of dictionaries with date and revenue
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Use the moment an order was last updated (e.g., when it became PAID/DELIVERED)
        # rather than its creation time, so revenue aligns with the actual payment date.
        # func.date() works across SQLite/PostgreSQL.
        query = (
            self.session.query(
                func.date(Order.updated_at).label('date'),
                func.sum(Order.total_amount).label('revenue')
            )
            .filter(
                and_(
                    Order.updated_at >= start_date,
                    Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED])
                )
            )
            .group_by(func.date(Order.updated_at))
            .order_by(func.date(Order.updated_at))
        )
        
        results = query.all()
        
        return [
            {
                "date": str(date) if date else "",
                "revenue": int(revenue) if revenue else 0
            }
            for date, revenue in results
        ]
    
    def get_top_selling_products(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top selling products by quantity sold.
        
        Args:
            limit: Maximum number of products to return
        
        Returns:
            List of dictionaries with product info and quantity sold
        """
        results = (
            self.session.query(
                Product.id,
                Product.name,
                func.sum(OrderItem.quantity).label('quantity_sold'),
                func.sum(OrderItem.subtotal).label('revenue')
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
            .group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                "product_id": product_id,
                "product_name": product_name,
                "quantity_sold": int(quantity_sold) if quantity_sold else 0,
                "revenue": int(revenue) if revenue else 0
            }
            for product_id, product_name, quantity_sold, revenue in results
        ]
    
    def get_total_sold_by_product(self) -> List[Dict[str, any]]:
        """
        Get total sold quantity by product.
        
        Returns:
            List of dictionaries with product info and total sold
        """
        results = (
            self.session.query(
                Product.id,
                Product.name,
                func.sum(OrderItem.quantity).label('total_sold'),
                func.sum(OrderItem.subtotal).label('revenue')
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
            .group_by(Product.id, Product.name)
            .all()
        )
        
        return [
            {
                "product_id": product_id,
                "product_name": product_name,
                "total_sold": int(total_sold) if total_sold else 0,
                "revenue": int(revenue) if revenue else 0
            }
            for product_id, product_name, total_sold, revenue in results
        ]
    
    def get_total_sold_all_products(self) -> int:
        """
        Get total sold quantity for all products.
        
        Returns:
            Total quantity sold
        """
        result = (
            self.session.query(func.sum(OrderItem.quantity))
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
            .scalar()
        )
        
        return int(result) if result else 0
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get recent orders.
        
        Args:
            limit: Maximum number of orders to return
        
        Returns:
            List of recent orders with basic info
        """
        orders = (
            self.session.query(Order)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                "id": order.id,
                "user_id": order.user_id,
                "status": order.status.value,
                "total_amount": order.total_amount,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
            for order in orders
        ]
    
    def get_statistics_overview(self) -> Dict[str, any]:
        """
        Get comprehensive statistics overview.
        
        Returns:
            Dictionary with all key statistics
        """
        return {
            "total_orders": self.get_total_orders_count(),
            "total_orders_today": self.get_total_orders_count("today"),
            "total_orders_this_week": self.get_total_orders_count("this_week"),
            "total_orders_this_month": self.get_total_orders_count("this_month"),
            "total_revenue": self.get_total_revenue(),
            "total_revenue_today": self.get_total_revenue("today"),
            "total_revenue_this_week": self.get_total_revenue("this_week"),
            "total_revenue_this_month": self.get_total_revenue("this_month"),
            "orders_by_status": self.get_orders_by_status(),
            "orders_by_product": self.get_orders_by_product(),
            "top_selling_products": self.get_top_selling_products(limit=10),
            "total_sold_all_products": self.get_total_sold_all_products(),
            "revenue_over_time_daily": self.get_revenue_over_time(interval="daily", days=30),
            "revenue_over_time_weekly": self.get_revenue_over_time(interval="weekly", days=90),
            "revenue_over_time_monthly": self.get_revenue_over_time(interval="monthly", days=365),
            "recent_orders": self.get_recent_orders(limit=10),
        }

