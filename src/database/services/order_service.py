"""
Order service layer for business logic.
"""

import secrets
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from src.database.models import Order, OrderItem
from src.database.models.bot_user import BotUser
from src.database.models.enums import OrderStatus
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.variation_service import VariationService


class OrderService:
    """Service for order operations."""

    def __init__(self, session: Session):
        """
        Initialize order service.

        Args:
            session: Database session
        """
        self.session = session
        self.variation_service = VariationService(session)

    def generate_order_id(self) -> str:
        """
        Generate a unique order ID.

        Returns:
            Order ID string
        """
        prefix = AppSettingsService(self.session).get_settings().order_prefix
        return f"{prefix}{uuid.uuid4().hex[:8]}"

    def generate_order_item_id(self) -> str:
        """
        Generate a unique order item ID.

        Returns:
            Order item ID string
        """
        return f"item_{uuid.uuid4().hex[:8]}"

    def generate_payos_order_code(self) -> int:
        """
        Generate a PayOS-compatible orderCode (integer).

        We keep this within signed 32-bit range to avoid any possible limitations,
        and ensure uniqueness with a DB check + retry.
        Uniqueness is checked across both the orders and topup_orders tables so that
        codes never collide between the two payment tables.
        """
        from src.database.models.topup_order import TopupOrder

        # 9-digit range (< 2^31) keeps it safe and still very low collision risk.
        for _ in range(30):
            candidate = 100_000_000 + secrets.randbelow(900_000_000)
            exists_order = (
                self.session.query(Order)
                .filter(Order.payos_order_code == candidate)
                .first()
            )
            exists_topup = (
                self.session.query(TopupOrder)
                .filter(TopupOrder.payos_order_code == candidate)
                .first()
            )
            if not exists_order and not exists_topup:
                return candidate
        raise RuntimeError("Unable to generate unique PayOS orderCode after retries")

    def validate_stock(
        self, variation_id: str, quantity: int, include_bonus: bool = True
    ) -> bool:
        """
        Validate that sufficient stock is available including bonus items.

        Args:
            variation_id: Variation ID
            quantity: Requested quantity
            include_bonus: If True, include bonus items in validation

        Returns:
            True if stock is available, False otherwise
        """
        variation = self.variation_service.get_variation_by_id(variation_id)
        if not variation:
            return False

        # Get actual available stock based on delivery type
        actual_stock = self._get_actual_stock(variation_id)

        if quantity <= 0:
            return False

        # Calculate total items including bonus
        total_items = quantity
        if include_bonus:
            from src.database.services.bonus_tier_service import BonusTierService

            bonus_service = BonusTierService(self.session)
            bonus_tier = bonus_service.get_applicable_bonus(
                variation_id, quantity, actual_stock
            )
            if bonus_tier:
                total_items = quantity + bonus_tier.bonus_quantity

        return actual_stock >= total_items

    def _get_actual_stock(self, variation_id: str) -> int:
        """
        Get actual available stock for a variation based on product delivery type.

        Args:
            variation_id: Variation ID

        Returns:
            Actual available stock count
        """
        from src.database.models.enums import DeliveryType
        from src.database.services.product_service import ProductService

        variation = self.variation_service.get_variation_by_id(variation_id)
        if not variation:
            return 0

        product_service = ProductService(self.session)
        product = product_service.get_product_by_id(variation.product_id)
        if not product:
            return 0

        if product.delivery_type == DeliveryType.PRE_UPLOADED:
            # For PRE_UPLOADED products, calculate from available pre-uploaded products
            return self.variation_service.calculate_stock_from_pre_uploaded(
                variation_id
            )
        if product.delivery_type == DeliveryType.UPGRADE:
            # UPGRADE products are not inventory-backed — only is_active gates ordering.
            return 999_999
        # For SUPPLIER_BASED products, use the stock field directly
        return variation.stock

    def calculate_total(self, variation_id: str, quantity: int) -> int:
        """
        Calculate total price for an order item.

        Args:
            variation_id: Variation ID
            quantity: Quantity

        Returns:
            Total price in VND
        """
        variation = self.variation_service.get_variation_by_id(variation_id)
        if not variation:
            raise ValueError(f"Variation {variation_id} not found")
        return variation.price * quantity

    def create_order(
        self,
        user_id: int,
        variation_id: str,
        quantity: int,
        bonus_quantity: int = 0,
        discount_tier=None,
    ) -> Order:
        """
        Create a new order from user selection.

        Args:
            user_id: Telegram user ID
            variation_id: Selected variation ID
            quantity: Order quantity
            bonus_quantity: Number of bonus items (0 if no bonus)
            discount_tier: Optional DiscountTier instance to apply

        Returns:
            Created Order instance

        Raises:
            ValueError: If stock is insufficient or variation not found
        """
        # Validate stock including bonus
        total_items = quantity + bonus_quantity
        actual_stock = self._get_actual_stock(variation_id)

        if actual_stock < total_items or quantity <= 0:
            variation = self.variation_service.get_variation_by_id(variation_id)
            if not variation:
                raise ValueError(f"Variation {variation_id} not found")
            raise ValueError(
                f"Insufficient stock. Available: {actual_stock}, Requested: {total_items} "
                f"(quantity: {quantity} + bonus: {bonus_quantity})"
            )

        # Get variation and product
        variation = self.variation_service.get_variation_by_id(variation_id)
        if not variation:
            raise ValueError(f"Variation {variation_id} not found")

        # Calculate total — apply discount if provided
        if discount_tier is not None:
            from src.database.services.discount_tier_service import DiscountTierService

            discount_service = DiscountTierService(self.session)
            total_amount, discount_amount = discount_service.calculate_discounted_total(
                variation.price, quantity, discount_tier
            )
        else:
            total_amount = self.calculate_total(variation_id, quantity)
            discount_amount = 0

        # Generate order ID
        order_id = self.generate_order_id()

        # Create order
        order = Order(
            id=order_id,
            user_id=user_id,
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            discount_amount=discount_amount,
        )
        self.session.add(order)

        # Create order item
        order_item = OrderItem(
            id=self.generate_order_item_id(),
            order_id=order_id,
            product_id=variation.product_id,
            variation_id=variation_id,
            quantity=quantity,
            bonus_quantity=bonus_quantity,
            unit_price=variation.price,
            subtotal=total_amount,
            discount_amount=discount_amount,
        )
        self.session.add(order_item)

        # For PRE_UPLOADED products, atomically reserve the exact rows now so no
        # concurrent order can claim the same stock while this order is PENDING.
        from src.database.models.enums import DeliveryType
        from src.database.services.pre_uploaded_service import PreUploadedService
        from src.database.services.product_service import ProductService

        product_service = ProductService(self.session)
        product = product_service.get_product_by_id(variation.product_id)

        if product and product.delivery_type == DeliveryType.PRE_UPLOADED:
            self.session.flush()  # write order/item rows before the UPDATE subquery
            pre_service = PreUploadedService(self.session)
            reserved = pre_service.reserve_products_for_order(
                order_id, variation_id, total_items
            )
            if reserved < total_items:
                self.session.rollback()
                raise ValueError(
                    f"Insufficient stock. Could only reserve {reserved} of {total_items} items."
                )

        # Commit transaction (includes order, order item, and any reservations)
        self.session.commit()
        self.session.refresh(order)

        return order

    def get_order_by_id(self, order_id: str) -> Order | None:
        """
        Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order instance or None if not found
        """
        return self.session.query(Order).filter_by(id=order_id).first()

    def get_order_by_payos_code(self, order_code: int) -> Order | None:
        """Get order by numeric PayOS orderCode."""
        return self.session.query(Order).filter(Order.payos_order_code == order_code).first()

    def get_oldest_awaiting_upgrade_order(self, user_id: int) -> Order | None:
        """
        Get the oldest order from this user that is waiting for upgrade
        account info (UPGRADE delivery type, post-payment, customer hasn't
        replied yet).
        """
        return (
            self.session.query(Order)
            .filter_by(user_id=user_id, awaiting_upgrade_info=True)
            .order_by(Order.created_at.asc())
            .first()
        )

    def get_order_by_upgrade_prompt_msg_id(
        self, user_id: int, message_id: int
    ) -> Order | None:
        """
        Find an UPGRADE order by the Telegram message ID of the account-info
        prompt sent to the customer. Used to relay additional customer replies
        (sent after awaiting_upgrade_info has already been cleared).
        """
        return (
            self.session.query(Order)
            .filter_by(user_id=user_id, upgrade_prompt_msg_id=message_id)
            .first()
        )

    def get_user_orders(
        self,
        user_id: int,
        status: OrderStatus | None = None,
        limit: int = 50,
    ) -> list[Order]:
        """
        Get orders for a user.

        Args:
            user_id: Telegram user ID
            status: Optional status filter
            limit: Maximum number of orders to return

        Returns:
            List of Order instances
        """
        query = self.session.query(Order).filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(Order.created_at.desc()).limit(limit).all()

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        payment_transaction_id: str | None = None,
    ) -> Order | None:
        """
        Update order status.

        Args:
            order_id: Order ID
            status: New status
            payment_transaction_id: Optional payment transaction ID

        Returns:
            Updated Order instance or None if not found
        """
        order = self.get_order_by_id(order_id)
        if not order:
            return None

        order.status = status
        if status == OrderStatus.PAID and order.paid_at is None:
            order.paid_at = func.now()
        if payment_transaction_id:
            order.payment_transaction_id = payment_transaction_id

        self.session.commit()
        self.session.refresh(order)
        return order

    def decrease_stock(self, variation_id: str, quantity: int) -> None:
        """
        Decrease stock for a variation (called after payment confirmation).

        Args:
            variation_id: Variation ID
            quantity: Quantity to decrease

        Raises:
            ValueError: If stock is insufficient
        """
        self.variation_service.decrease_stock(variation_id, quantity)

    def list_orders(
        self,
        page: int = 1,
        per_page: int = 15,
        status: OrderStatus | None = None,
        user_id: int | None = None,
        product_id: str | None = None,
        search: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        delivery_search: str | None = None,
        delivery_start_date: str | None = None,
        delivery_end_date: str | None = None,
    ) -> list[Order]:
        """
        List orders with pagination, filters, and search.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            status: Filter by order status
            user_id: Filter by user ID
            product_id: Filter by product ID (orders containing this product)
            search: Search term (searches order ID)
            sort_by: Field to sort by (created_at, total_amount, status)
            sort_order: Sort order (asc, desc)
            start_date: Filter orders from this date (ISO format)
            end_date: Filter orders until this date (ISO format)
            delivery_search: Search term for delivered content (product_data fuzzy match)
            delivery_start_date: Filter orders delivered from this date (ISO format)
            delivery_end_date: Filter orders delivered until this date (ISO format)

        Returns:
            List of Order instances
        """
        from datetime import datetime

        from sqlalchemy import and_, exists

        from src.database.models.pre_uploaded_product import PreUploadedProduct

        query = self.session.query(Order)

        # Apply status filter
        if status:
            query = query.filter_by(status=status)

        # Apply user_id filter
        if user_id:
            query = query.filter_by(user_id=user_id)

        # Apply product_id filter (through order items)
        if product_id:
            query = query.join(OrderItem).filter(OrderItem.product_id == product_id)

        # Apply search filter (order ID)
        if search:
            query = query.filter(Order.id.ilike(f"%{search}%"))

        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.filter(Order.created_at >= start_dt)
            except ValueError:
                pass  # Invalid date format, ignore

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.filter(Order.created_at <= end_dt)
            except ValueError:
                pass  # Invalid date format, ignore

        # Apply delivery filters via correlated EXISTS subquery
        delivery_start_dt = None
        delivery_end_dt = None
        if delivery_start_date:
            try:
                delivery_start_dt = datetime.fromisoformat(
                    delivery_start_date.replace("Z", "+00:00")
                )
            except ValueError:
                pass  # Invalid date format, ignore
        if delivery_end_date:
            try:
                delivery_end_dt = datetime.fromisoformat(
                    delivery_end_date.replace("Z", "+00:00")
                )
            except ValueError:
                pass  # Invalid date format, ignore

        if delivery_search or delivery_start_dt or delivery_end_dt:
            conds = [
                PreUploadedProduct.used_by_order_id == Order.id,
                PreUploadedProduct.is_used.is_(True),
            ]
            if delivery_search:
                conds.append(
                    PreUploadedProduct.product_data.ilike(f"%{delivery_search}%")
                )
            if delivery_start_dt:
                conds.append(PreUploadedProduct.used_at >= delivery_start_dt)
            if delivery_end_dt:
                conds.append(PreUploadedProduct.used_at <= delivery_end_dt)
            query = query.filter(exists().where(and_(*conds)))

        # Apply sorting
        if sort_by == "created_at":
            if sort_order == "desc":
                query = query.order_by(Order.created_at.desc())
            else:
                query = query.order_by(Order.created_at.asc())
        elif sort_by == "total_amount":
            if sort_order == "desc":
                query = query.order_by(Order.total_amount.desc())
            else:
                query = query.order_by(Order.total_amount.asc())
        elif sort_by == "status":
            if sort_order == "desc":
                query = query.order_by(Order.status.desc())
            else:
                query = query.order_by(Order.status.asc())
        else:
            # Default: newest first
            query = query.order_by(Order.created_at.desc())

        # Apply pagination
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page).all()

    def get_total_count(
        self,
        status: OrderStatus | None = None,
        user_id: int | None = None,
        product_id: str | None = None,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        delivery_search: str | None = None,
        delivery_start_date: str | None = None,
        delivery_end_date: str | None = None,
    ) -> int:
        """
        Get total count of orders matching filters.

        Args:
            status: Filter by order status
            user_id: Filter by user ID
            product_id: Filter by product ID
            search: Search term
            start_date: Filter orders from this date
            end_date: Filter orders until this date
            delivery_search: Search term for delivered content (product_data fuzzy match)
            delivery_start_date: Filter orders delivered from this date (ISO format)
            delivery_end_date: Filter orders delivered until this date (ISO format)

        Returns:
            Total count
        """
        from datetime import datetime

        from sqlalchemy import and_, exists, func

        from src.database.models.pre_uploaded_product import PreUploadedProduct

        query = self.session.query(func.count(Order.id))

        # Apply same filters as list_orders
        if status:
            query = query.filter_by(status=status)

        if user_id:
            query = query.filter_by(user_id=user_id)

        if product_id:
            query = query.join(OrderItem).filter(OrderItem.product_id == product_id)

        if search:
            query = query.filter(Order.id.ilike(f"%{search}%"))

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.filter(Order.created_at >= start_dt)
            except ValueError:
                pass

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.filter(Order.created_at <= end_dt)
            except ValueError:
                pass

        # Apply delivery filters via correlated EXISTS subquery (identical to list_orders)
        delivery_start_dt = None
        delivery_end_dt = None
        if delivery_start_date:
            try:
                delivery_start_dt = datetime.fromisoformat(
                    delivery_start_date.replace("Z", "+00:00")
                )
            except ValueError:
                pass  # Invalid date format, ignore
        if delivery_end_date:
            try:
                delivery_end_dt = datetime.fromisoformat(
                    delivery_end_date.replace("Z", "+00:00")
                )
            except ValueError:
                pass  # Invalid date format, ignore

        if delivery_search or delivery_start_dt or delivery_end_dt:
            conds = [
                PreUploadedProduct.used_by_order_id == Order.id,
                PreUploadedProduct.is_used.is_(True),
            ]
            if delivery_search:
                conds.append(
                    PreUploadedProduct.product_data.ilike(f"%{delivery_search}%")
                )
            if delivery_start_dt:
                conds.append(PreUploadedProduct.used_at >= delivery_start_dt)
            if delivery_end_dt:
                conds.append(PreUploadedProduct.used_at <= delivery_end_dt)
            query = query.filter(exists().where(and_(*conds)))

        return query.scalar() or 0

    def get_buyer_info_map(self, telegram_user_ids: list[int]) -> dict[int, dict]:
        """Return {telegram_user_id: {username, name}} for a batch of IDs."""
        if not telegram_user_ids:
            return {}
        rows = (
            self.session.query(BotUser)
            .filter(BotUser.telegram_user_id.in_(telegram_user_ids))
            .all()
        )
        result = {}
        for u in rows:
            parts = [p for p in (u.first_name, u.last_name) if p]
            result[u.telegram_user_id] = {
                "username": u.username,
                "name": " ".join(parts) if parts else None,
            }
        return result

    def list_recently_paid(self, since: datetime, limit: int = 50) -> list:
        """Orders paid after `since`, ascending by paid_at, items eager-loaded."""
        stmt = (
            select(Order)
            .where(Order.paid_at.isnot(None), Order.paid_at > since)
            .order_by(Order.paid_at.asc())
            .limit(limit)
            .options(
                joinedload(Order.items).joinedload(OrderItem.product),
                joinedload(Order.items).joinedload(OrderItem.variation),
            )
        )
        return self.session.execute(stmt).unique().scalars().all()

    def get_order_with_details(self, order_id: str) -> dict | None:
        """
        Get order with all related details (items, products, variations).

        Args:
            order_id: Order ID

        Returns:
            Dictionary with order details or None if not found
        """
        order = self.get_order_by_id(order_id)
        if not order:
            return None

        # If this is a PRE_UPLOADED order, delivery data is stored in pre_uploaded_products
        # rows linked to the order via used_by_order_id. We attach that data per item.
        delivered_by_variation: dict[str, list] = {}
        try:
            from src.database.models.pre_uploaded_product import PreUploadedProduct
            from src.database.services.pre_uploaded_service import PreUploadedService

            pre_uploaded_service = PreUploadedService(self.session)
            delivered_rows = (
                self.session.query(PreUploadedProduct)
                .filter_by(used_by_order_id=order_id, is_used=True)
                .all()
            )

            def _format_delivered_data(data) -> str:
                # The PreUploadedService parser normalizes to a dict; convert to readable text.
                if not isinstance(data, dict) or not data:
                    return ""
                if "delivery_data" in data and len(data) == 1:
                    return str(data["delivery_data"])
                if "value" in data and len(data) == 1:
                    return str(data["value"])
                # Multi-key dict: show key/value pairs line-by-line
                lines = []
                for k, v in data.items():
                    lines.append(f"{k}: {v}")
                return "\n".join(lines)

            for row in delivered_rows:
                vid = getattr(row, "variation_id", None)
                if not vid:
                    continue
                parsed = pre_uploaded_service.get_product_data(row)
                delivered_by_variation.setdefault(vid, []).append(
                    {
                        "id": row.id,
                        "used_at": row.used_at.isoformat() if row.used_at else None,
                        "display": _format_delivered_data(parsed),
                        "data": parsed if isinstance(parsed, dict) else None,
                    }
                )
        except Exception:  # noqa: BLE001
            # Best-effort: do not break order details if delivery rows cannot be loaded
            delivered_by_variation = {}

        # Get order items with product and variation info
        items = []
        for item in order.items:
            item_data = {
                "id": item.id,
                "quantity": item.quantity,
                "bonus_quantity": item.bonus_quantity or 0,
                "total_items": item.quantity + (item.bonus_quantity or 0),
                "unit_price": item.unit_price,
                "subtotal": item.subtotal,
                "discount_amount": item.discount_amount or 0,
            }

            # Add product info if available
            if item.product:
                item_data["product"] = {
                    "id": item.product.id,
                    "name": item.product.name,
                    "description": item.product.description,
                }
            else:
                item_data["product"] = None

            # Add variation info if available
            if item.variation:
                item_data["variation"] = {
                    "id": item.variation.id,
                    "name": item.variation.name,
                    "price": item.variation.price,
                }
            else:
                item_data["variation"] = None

            # Attach delivered data (pre-uploaded products) when present
            if item.variation_id:
                delivered_products = delivered_by_variation.get(item.variation_id, [])
                item_data["delivered_products"] = delivered_products
                item_data["delivered_count"] = len(delivered_products)
            else:
                item_data["delivered_products"] = []
                item_data["delivered_count"] = 0

            items.append(item_data)

        # Get supplier orders if any
        supplier_orders = []
        for so in order.supplier_orders:
            supplier_orders.append(
                {
                    "id": so.id,
                    "supplier_id": so.supplier_id,
                    "status": so.status.value,
                    "created_at": so.created_at.isoformat(),
                    "updated_at": so.updated_at.isoformat(),
                }
            )

        buyer_map = self.get_buyer_info_map([order.user_id])
        buyer = buyer_map.get(order.user_id, {})

        return {
            "id": order.id,
            "user_id": order.user_id,
            "buyer_username": buyer.get("username"),
            "buyer_name": buyer.get("name"),
            "status": order.status.value,
            "total_amount": order.total_amount,
            "discount_amount": order.discount_amount or 0,
            "payment_transaction_id": order.payment_transaction_id,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "items": items,
            "supplier_orders": supplier_orders,
        }

    def cancel_order(self, order_id: str) -> Order:
        """
        Cancel an order (only PENDING orders can be cancelled).

        Uses an atomic conditional UPDATE so concurrent calls cannot race —
        the second caller will see rowcount == 0 and receive a ValueError.
        This is the contract expected by AutoCancelService (catches ValueError).

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancelled Order instance

        Raises:
            ValueError: If order not found or cannot be cancelled (not PENDING)
        """
        r = self.session.execute(
            update(Order)
            .where(Order.id == order_id, Order.status == OrderStatus.PENDING)
            .values(status=OrderStatus.CANCELLED)
        )
        if r.rowcount == 0:
            # Distinguish not-found from already-processed.
            existing = self.get_order_by_id(order_id)
            if existing is None:
                raise ValueError(f"Order {order_id} not found")
            raise ValueError(
                f"Order {order_id} is not in PENDING status. "
                f"Current status: {existing.status.value}"
            )

        # Release any pre-uploaded product reservations in the same transaction.
        from src.database.services.pre_uploaded_service import PreUploadedService

        PreUploadedService(self.session).release_reservations_for_order(order_id)

        self.session.commit()
        order = self.get_order_by_id(order_id)
        return order  # type: ignore[return-value]
