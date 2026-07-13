"""
Statistics service for order and sales analytics.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from src.database.models import Order, OrderItem, Product, BotUser, TopupOrder
from src.database.models.enums import OrderStatus, TopupStatus
from src.utils.datetime_format import resolve_tz


class StatisticsService:
    """Service for order and sales statistics."""

    def __init__(self, session: Session):
        """
        Initialize statistics service.

        Args:
            session: Database session
        """
        self.session = session

    def _app_tz(self):
        """Return the configured app timezone as a ZoneInfo object."""
        from src.database.services.app_settings_service import AppSettingsService
        tz_name = AppSettingsService(self.session).get_settings().timezone
        return resolve_tz(tz_name)

    def _get_date_range(self, period: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Get date range for period filter, computed in the app timezone and returned
        as naive UTC datetimes for comparison against naive-UTC DB columns.

        Args:
            period: Period string ('today', 'this_week', 'this_month', None for all time)

        Returns:
            Tuple of (start_date, end_date) as naive UTC, or (None, None) for all time
        """
        tz = self._app_tz()
        now_local = datetime.now(tz=tz)

        def to_naive_utc(dt_aware: datetime) -> datetime:
            return dt_aware.astimezone(timezone.utc).replace(tzinfo=None)

        if period == "today":
            # Midnight in app tz → naive UTC
            start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            return to_naive_utc(start_local), to_naive_utc(now_local)
        elif period == "this_week":
            start_local = now_local - timedelta(days=7)
            return to_naive_utc(start_local), to_naive_utc(now_local)
        elif period == "this_month":
            start_local = now_local - timedelta(days=30)
            return to_naive_utc(start_local), to_naive_utc(now_local)
        else:
            return None, None
    
    def get_total_orders_count(
        self,
        period: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Get total orders count.

        Args:
            period: Period filter ('today', 'this_week', 'this_month', None for all time)
            start_date: Explicit range start (overrides period)
            end_date: Explicit range end (overrides period)

        Returns:
            Total orders count
        """
        query = self.session.query(func.count(Order.id))

        if start_date or end_date:
            if start_date:
                query = query.filter(Order.created_at >= start_date)
            if end_date:
                query = query.filter(Order.created_at <= end_date)
        elif period:
            sd, ed = self._get_date_range(period)
            if sd and ed:
                query = query.filter(and_(Order.created_at >= sd, Order.created_at <= ed))

        return query.scalar() or 0

    def get_total_revenue(
        self,
        period: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Get total revenue (sum of paid and delivered orders).

        Date window is applied to Order.updated_at (payment time).

        Args:
            period: Period filter ('today', 'this_week', 'this_month', None for all time)
            start_date: Explicit range start (overrides period)
            end_date: Explicit range end (overrides period)

        Returns:
            Total revenue in VND
        """
        query = self.session.query(func.sum(Order.total_amount)).filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED])
        )

        if start_date or end_date:
            if start_date:
                query = query.filter(Order.updated_at >= start_date)
            if end_date:
                query = query.filter(Order.updated_at <= end_date)
        elif period:
            sd, ed = self._get_date_range(period)
            if sd and ed:
                query = query.filter(and_(Order.updated_at >= sd, Order.updated_at <= ed))

        result = query.scalar()
        return int(result) if result else 0

    def get_vendor_revenue(
        self,
        period: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Get vendor cash revenue = QR-paid orders + PAID topups, excluding balance payments.

        QR orders: any non-balance payment provider, status PAID/DELIVERED.
        Topups: TopupOrder where status=PAID.
        Both windowed on updated_at.

        Args:
            period: Period filter ('today', 'this_week', 'this_month', None for all time)
            start_date: Explicit range start (overrides period)
            end_date: Explicit range end (overrides period)

        Returns:
            Total vendor revenue in VND
        """
        # Resolve time window (naive UTC)
        if start_date or end_date:
            sd: Optional[datetime] = start_date
            ed: Optional[datetime] = end_date
        elif period:
            sd, ed = self._get_date_range(period)
        else:
            sd, ed = None, None

        # QR orders revenue
        qr_query = self.session.query(func.sum(Order.total_amount)).filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]),
            Order.payment_provider.is_not(None),
            Order.payment_provider != "balance",
        )
        if sd:
            qr_query = qr_query.filter(Order.updated_at >= sd)
        if ed:
            qr_query = qr_query.filter(Order.updated_at <= ed)

        # Paid topups revenue
        topup_query = self.session.query(func.sum(TopupOrder.amount)).filter(
            TopupOrder.status == TopupStatus.PAID,
        )
        if sd:
            topup_query = topup_query.filter(TopupOrder.updated_at >= sd)
        if ed:
            topup_query = topup_query.filter(TopupOrder.updated_at <= ed)

        qr_result = qr_query.scalar() or 0
        topup_result = topup_query.scalar() or 0
        return int(qr_result) + int(topup_result)

    def get_orders_by_status(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get orders grouped by status.

        Returns:
            Dictionary mapping status to count
        """
        query = self.session.query(Order.status, func.count(Order.id)).group_by(Order.status)
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        return {status.value: count for status, count in query.all()}
    
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
        days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, any]]:
        """
        Get revenue over time.

        Args:
            interval: Time interval ('daily', 'weekly', 'monthly')
            days: Number of days to look back (ignored when start_date is provided)
            start_date: Explicit range start
            end_date: Explicit range end

        Returns:
            List of dictionaries with date and revenue
        """
        now = datetime.now(timezone.utc)
        effective_start = start_date if start_date is not None else now - timedelta(days=days)
        effective_end = end_date if end_date is not None else now

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
                    Order.updated_at >= effective_start,
                    Order.updated_at <= effective_end,
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
    
    def get_top_selling_products(
        self,
        limit: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, any]]:
        """
        Get top selling products by quantity sold.

        Args:
            limit: Maximum number of products to return
            start_date: Explicit range start
            end_date: Explicit range end

        Returns:
            List of dictionaries with product info and quantity sold
        """
        query = (
            self.session.query(
                Product.id,
                Product.name,
                func.sum(OrderItem.quantity).label('quantity_sold'),
                func.sum(OrderItem.subtotal).label('revenue')
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
        )
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        results = (
            query.group_by(Product.id, Product.name)
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

    def get_total_sold_by_product(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, any]]:
        """
        Get total sold quantity by product.

        Returns:
            List of dictionaries with product info and total sold, sorted by revenue desc
        """
        query = (
            self.session.query(
                Product.id,
                Product.name,
                func.sum(OrderItem.quantity).label('total_sold'),
                func.sum(OrderItem.subtotal).label('revenue')
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
        )
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        results = (
            query.group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.subtotal).desc())
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
    
    def get_total_sold_all_products(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Get total sold quantity for all products.

        Returns:
            Total quantity sold
        """
        query = (
            self.session.query(func.sum(OrderItem.quantity))
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
        )
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        return int(query.scalar() or 0)

    def get_recent_orders(
        self,
        limit: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, any]]:
        """
        Get recent orders.

        Args:
            limit: Maximum number of orders to return
            start_date: Explicit range start
            end_date: Explicit range end

        Returns:
            List of recent orders with basic info
        """
        query = self.session.query(Order)
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        orders = (
            query.order_by(Order.created_at.desc())
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
    
    def get_funnel(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Conversion funnel: counts per status stage in pipeline order."""
        stages = [
            OrderStatus.PENDING,
            OrderStatus.PAID,
            OrderStatus.PROCESSING,
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
        ]
        result = []
        for status in stages:
            q = self.session.query(func.count(Order.id)).filter(Order.status == status)
            if start_date:
                q = q.filter(Order.created_at >= start_date)
            if end_date:
                q = q.filter(Order.created_at <= end_date)
            result.append({"status": status.value, "count": q.scalar() or 0})
        return result

    def get_orders_heatmap(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, int]]:
        """Hour×weekday heatmap (168 cells). Returns [{day, hour, count}]."""
        q = self.session.query(
            extract("dow", Order.created_at).label("day"),
            extract("hour", Order.created_at).label("hour"),
            func.count(Order.id).label("count"),
        )
        if start_date:
            q = q.filter(Order.created_at >= start_date)
        if end_date:
            q = q.filter(Order.created_at <= end_date)
        q = q.group_by("day", "hour")

        # Build full 7×24 grid
        grid: Dict[Tuple[int, int], int] = {}
        for row in q.all():
            grid[(int(row.day), int(row.hour))] = int(row.count)

        result = []
        for day in range(7):
            for hour in range(24):
                result.append({"day": day, "hour": hour, "count": grid.get((day, hour), 0)})
        return result

    def get_revenue_delta(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[float]:
        """Revenue % change vs. equal-length prior period. None when no prior data."""
        period_len = end_date - start_date
        prev_start = start_date - period_len
        prev_end = start_date

        def _revenue(s: datetime, e: datetime) -> int:
            return (
                self.session.query(func.sum(Order.total_amount))
                .filter(
                    and_(
                        Order.created_at >= s,
                        Order.created_at < e,
                        Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]),
                    )
                )
                .scalar()
                or 0
            )

        current = _revenue(start_date, end_date)
        previous = _revenue(prev_start, prev_end)
        if previous == 0:
            return None
        return round((current - previous) / previous * 100, 1)

    def get_orders_delta(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[float]:
        """Orders % change vs. equal-length prior period."""
        period_len = end_date - start_date
        prev_start = start_date - period_len
        prev_end = start_date

        def _count(s: datetime, e: datetime) -> int:
            return (
                self.session.query(func.count(Order.id))
                .filter(and_(Order.created_at >= s, Order.created_at < e))
                .scalar()
                or 0
            )

        current = _count(start_date, end_date)
        previous = _count(prev_start, prev_end)
        if previous == 0:
            return None
        return round((current - previous) / previous * 100, 1)

    def get_revenue_by_product_with_delta(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Revenue by product with % change vs equal-length prior period."""
        current = self.get_total_sold_by_product(start_date, end_date)
        period_len = end_date - start_date
        prev_start = start_date - period_len
        previous = self.get_total_sold_by_product(prev_start, start_date)
        prev_lookup = {p["product_id"]: p["revenue"] for p in previous}

        result = []
        for item in current:
            prev_rev = prev_lookup.get(item["product_id"], 0)
            pct_change: Optional[float] = (
                round((item["revenue"] - prev_rev) / prev_rev * 100, 1)
                if prev_rev > 0
                else None
            )
            result.append({**item, "pct_change": pct_change})
        return result

    def get_user_stats(self) -> Dict[str, int]:
        """Count all users who pressed /start and how many are still active (not blocked)."""
        started = (
            self.session.query(func.count(BotUser.id))
            .filter(BotUser.has_started.is_(True))
            .scalar()
            or 0
        )
        active = (
            self.session.query(func.count(BotUser.id))
            .filter(BotUser.has_started.is_(True), BotUser.is_active.is_(True))
            .scalar()
            or 0
        )
        return {"started": int(started), "active": int(active)}

    def get_active_users(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Dict[str, Any]:
        """
        Count active users for a period.

        With a date range: counts distinct buyers (users with PAID/DELIVERED orders)
        in the current period and computes % change vs the equal-length prior period.
        Without a range: returns total registered users (has_started=True).
        """
        if start_date and end_date:
            def _buyers(s: datetime, e: datetime) -> int:
                return (
                    self.session.query(func.count(Order.user_id.distinct()))
                    .filter(
                        and_(
                            Order.created_at >= s,
                            Order.created_at < e,
                            Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]),
                        )
                    )
                    .scalar()
                    or 0
                )

            current = _buyers(start_date, end_date)
            period_len = end_date - start_date
            previous = _buyers(start_date - period_len, start_date)
            pct_change: Optional[float] = (
                round((current - previous) / previous * 100, 1)
                if previous > 0
                else None
            )
            return {"current": current, "previous": previous, "pct_change": pct_change}
        else:
            count = (
                self.session.query(func.count(BotUser.id))
                .filter(BotUser.has_started.is_(True))
                .scalar()
                or 0
            )
            return {"current": count, "previous": 0, "pct_change": None}

    def get_statistics_overview(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics overview with optional range filter.

        Args:
            start_date: Range start (None = all time)
            end_date: Range end (None = now)

        Returns:
            Dictionary with all key statistics
        """
        base: Dict[str, Any] = {
            "total_orders": self.get_total_orders_count(start_date=start_date, end_date=end_date),
            "total_orders_today": self.get_total_orders_count("today"),
            "total_orders_this_week": self.get_total_orders_count("this_week"),
            "total_orders_this_month": self.get_total_orders_count("this_month"),
            "total_revenue": self.get_total_revenue(start_date=start_date, end_date=end_date),
            "total_revenue_today": self.get_total_revenue("today"),
            "total_revenue_this_week": self.get_total_revenue("this_week"),
            "total_revenue_this_month": self.get_total_revenue("this_month"),
            "vendor_revenue": self.get_vendor_revenue(start_date=start_date, end_date=end_date),
            "vendor_revenue_today": self.get_vendor_revenue("today"),
            "orders_by_status": self.get_orders_by_status(start_date, end_date),
            "orders_by_product": self.get_orders_by_product(),
            "top_selling_products": self.get_top_selling_products(limit=10, start_date=start_date, end_date=end_date),
            "total_sold_all_products": self.get_total_sold_all_products(start_date, end_date),
            "revenue_over_time_daily": self.get_revenue_over_time(interval="daily", days=30, start_date=start_date, end_date=end_date),
            "revenue_over_time_weekly": self.get_revenue_over_time(interval="weekly", days=90, start_date=start_date, end_date=end_date),
            "revenue_over_time_monthly": self.get_revenue_over_time(interval="monthly", days=365, start_date=start_date, end_date=end_date),
            "revenue_by_product": (
                self.get_revenue_by_product_with_delta(start_date, end_date)
                if start_date and end_date
                else self.get_total_sold_by_product(start_date, end_date)
            ),
            "recent_orders": self.get_recent_orders(limit=10, start_date=start_date, end_date=end_date),
            "funnel": self.get_funnel(start_date, end_date),
            "orders_heatmap": self.get_orders_heatmap(start_date, end_date),
            "active_users": self.get_active_users(start_date, end_date),
            "user_stats": self.get_user_stats(),
        }
        if start_date and end_date:
            base["revenue_delta"] = self.get_revenue_delta(start_date, end_date)
            base["orders_delta"] = self.get_orders_delta(start_date, end_date)
        else:
            base["revenue_delta"] = None
            base["orders_delta"] = None
        return base

    def get_top_buyers_today(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top buyers by total amount spent today (paid/delivered orders only).

        Returns:
            List of dicts with user_id, first_name, last_name, username, total_spent, order_count.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        results = (
            self.session.query(
                Order.user_id,
                BotUser.first_name,
                BotUser.last_name,
                BotUser.username,
                func.sum(Order.total_amount).label("total_spent"),
                func.count(Order.id).label("order_count"),
            )
            .join(BotUser, Order.user_id == BotUser.telegram_user_id)
            .filter(
                Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]),
                Order.created_at >= today_start,
            )
            .group_by(Order.user_id, BotUser.first_name, BotUser.last_name, BotUser.username)
            .order_by(func.sum(Order.total_amount).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "user_id": user_id,
                "first_name": first_name or "",
                "last_name": last_name or "",
                "username": username or "",
                "total_spent": int(total_spent) if total_spent else 0,
                "order_count": int(order_count) if order_count else 0,
            }
            for user_id, first_name, last_name, username, total_spent, order_count in results
        ]

    def _upgrade_orders_query(self):
        from sqlalchemy import select
        from src.database.models.order import Order
        from src.database.models.order_item import OrderItem
        from src.database.models.product import Product
        from src.database.models.enums import DeliveryType, OrderStatus

        # Orders that contain at least one UPGRADE-delivery product. Use a
        # subquery on order ids rather than a join: joining through OrderItem
        # multiplies rows for multi-item orders, and the DISTINCT needed to
        # dedup them (DISTINCT ON (orders.id)) conflicts with
        # ORDER BY created_at on PostgreSQL. The subquery sidesteps both.
        upgrade_order_ids = (
            select(OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(Product.delivery_type == DeliveryType.UPGRADE)
        )
        return (
            self.session.query(Order)
            .filter(
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PROCESSING]),
                Order.id.in_(upgrade_order_ids),
            )
            .order_by(Order.created_at.asc())
        )

    def get_todo_items(self) -> Dict[str, Any]:
        from src.database.services.pre_uploaded_service import PreUploadedService

        rows = self._upgrade_orders_query().all()
        upgrade_orders = [
            {
                "id": o.id,
                "status": o.status.value,
                "total_amount": o.total_amount,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in rows
        ]

        LOW_STOCK_THRESHOLD = 5
        inventory_stats = PreUploadedService(self.session).get_inventory_stats_by_product()

        aging_items: list = []
        low_stock_items: list = []
        for product in inventory_stats:
            for v in product["variants"]:
                base = {
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "variation_id": v["variation_id"],
                    "variation_name": v["variation_name"],
                    "in_stock": v["in_stock"],
                    "aging": v["aging"],
                    "expiring_soon": v["expiring_soon"],
                }
                if v["aging"] > 0 or v["expiring_soon"] > 0:
                    aging_items.append(base)
                if v["in_stock"] <= LOW_STOCK_THRESHOLD:
                    low_stock_items.append(base)

        return {
            "upgrade_orders": upgrade_orders,
            "upgrade_orders_count": len(upgrade_orders),
            "aging_inventory": aging_items,
            "aging_inventory_count": len(aging_items),
            "low_stock_inventory": low_stock_items,
            "low_stock_inventory_count": len(low_stock_items),
        }
