"""
Orders router.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func as sa_func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.order_service import OrderService
from src.database.models.enums import OrderStatus, DeliveryType
import csv
import io
from src.utils.datetime_format import to_utc_iso

logger = logging.getLogger(__name__)

router = APIRouter()


class OrderStatusUpdate(BaseModel):
    """Order status update schema."""

    status: str


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_orders(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(15, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    product_id: Optional[str] = Query(None, description="Filter by product ID"),
    search: Optional[str] = Query(None, description="Search by order ID"),
    sort_by: Optional[str] = Query(
        "created_at", description="Sort field: created_at, total_amount, status"
    ),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc, desc"),
    start_date: Optional[str] = Query(
        None, description="Filter from date (ISO format)"
    ),
    end_date: Optional[str] = Query(None, description="Filter until date (ISO format)"),
    delivery_search: Optional[str] = Query(
        None, description="Search by delivered content (fuzzy match on product_data)"
    ),
    delivery_start_date: Optional[str] = Query(
        None, description="Filter by delivery date from (ISO format, uses used_at)"
    ),
    delivery_end_date: Optional[str] = Query(
        None, description="Filter by delivery date until (ISO format, uses used_at)"
    ),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List orders with pagination, filters, and search.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        status: Filter by order status
        user_id: Filter by user ID
        product_id: Filter by product ID
        search: Search term (order ID)
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        start_date: Filter from date
        end_date: Filter until date
        delivery_search: Fuzzy search in delivered content (product_data)
        delivery_start_date: Filter by delivery date from (used_at)
        delivery_end_date: Filter by delivery date until (used_at)

    Returns:
        Paginated list of orders
    """
    service = OrderService(db)

    # Parse status enum if provided
    status_enum = None
    if status:
        try:
            status_enum = OrderStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )

    # Get orders with filters
    orders = service.list_orders(
        page=page,
        per_page=per_page,
        status=status_enum,
        user_id=user_id,
        product_id=product_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        start_date=start_date,
        end_date=end_date,
        delivery_search=delivery_search,
        delivery_start_date=delivery_start_date,
        delivery_end_date=delivery_end_date,
    )

    # Get total count with same filters
    total = service.get_total_count(
        status=status_enum,
        user_id=user_id,
        product_id=product_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        delivery_search=delivery_search,
        delivery_start_date=delivery_start_date,
        delivery_end_date=delivery_end_date,
    )

    buyer_map = service.get_buyer_info_map([o.user_id for o in orders])

    return {
        "items": [
            {
                "id": order.id,
                "user_id": order.user_id,
                "buyer_username": buyer_map.get(order.user_id, {}).get("username"),
                "buyer_name": buyer_map.get(order.user_id, {}).get("name"),
                "status": order.status.value,
                "total_amount": order.total_amount,
                "payment_transaction_id": order.payment_transaction_id,
                "created_at": to_utc_iso(order.created_at),
                "updated_at": to_utc_iso(order.updated_at),
            }
            for order in orders
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/export")
async def export_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    product_id: Optional[str] = Query(None, description="Filter by product ID"),
    search: Optional[str] = Query(None, description="Search by order ID"),
    start_date: Optional[str] = Query(
        None, description="Filter from date (ISO format)"
    ),
    end_date: Optional[str] = Query(None, description="Filter until date (ISO format)"),
    delivery_search: Optional[str] = Query(
        None, description="Search by delivered content (fuzzy match on product_data)"
    ),
    delivery_start_date: Optional[str] = Query(
        None, description="Filter by delivery date from (ISO format, uses used_at)"
    ),
    delivery_end_date: Optional[str] = Query(
        None, description="Filter by delivery date until (ISO format, uses used_at)"
    ),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Export orders to CSV.

    Args:
        status: Filter by order status
        user_id: Filter by user ID
        product_id: Filter by product ID
        search: Search term
        start_date: Filter from date
        end_date: Filter until date
        delivery_search: Fuzzy search in delivered content (product_data)
        delivery_start_date: Filter by delivery date from (used_at)
        delivery_end_date: Filter by delivery date until (used_at)

    Returns:
        CSV file with orders
    """
    service = OrderService(db)

    # Parse status enum if provided
    status_enum = None
    if status:
        try:
            status_enum = OrderStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )

    # Get all orders matching filters (no pagination for export)
    orders = service.list_orders(
        page=1,
        per_page=10000,  # Large limit for export
        status=status_enum,
        user_id=user_id,
        product_id=product_id,
        search=search,
        sort_by="created_at",
        sort_order="desc",
        start_date=start_date,
        end_date=end_date,
        delivery_search=delivery_search,
        delivery_start_date=delivery_start_date,
        delivery_end_date=delivery_end_date,
    )

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "Order ID",
            "User ID",
            "Status",
            "Total Amount (VND)",
            "Payment Transaction ID",
            "Created At",
            "Updated At",
        ]
    )

    # Write data
    for order in orders:
        writer.writerow(
            [
                order.id,
                order.user_id,
                order.status.value,
                order.total_amount,
                order.payment_transaction_id or "",
                to_utc_iso(order.created_at),
                to_utc_iso(order.updated_at),
            ]
        )

    # Return CSV as response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_export.csv"},
    )


@router.get("/recent-paid")
async def recent_paid(
    since: Optional[str] = Query(None, description="ISO8601; return orders paid after this"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Orders newly paid since `since`, for dashboard toast notifications."""
    service = OrderService(db)
    server_now = db.execute(select(sa_func.now())).scalar_one()

    # SQLite returns a string from func.now(); Postgres returns a datetime.
    # Coerce to datetime before passing to to_utc_iso.
    if isinstance(server_now, str):
        server_now = datetime.fromisoformat(server_now)

    orders_out = []
    if since:
        try:
            # URL query params decode '+' as ' '; re-normalize to '+' for timezone offsets.
            since_normalized = since.replace(" ", "+")
            since_dt = datetime.fromisoformat(since_normalized)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid 'since' timestamp: {since}",
            )
        # Compare naive-to-naive: DB timestamps are naive UTC.
        if since_dt.tzinfo is not None:
            since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)

        orders = service.list_recently_paid(since_dt)
        buyer_map = service.get_buyer_info_map([o.user_id for o in orders])
        for order in orders:
            orders_out.append({
                "id": order.id,
                "user_id": order.user_id,
                "buyer_username": buyer_map.get(order.user_id, {}).get("username"),
                "buyer_name": buyer_map.get(order.user_id, {}).get("name"),
                "total_amount": order.total_amount,
                "items": [
                    {
                        "product_name": item.product.name if item.product else None,
                        "variation_name": item.variation.name if item.variation else None,
                    }
                    for item in order.items
                ],
            })

    return {"server_now": to_utc_iso(server_now), "orders": orders_out}


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get order details by ID.

    Args:
        order_id: Order ID

    Returns:
        Order details with items and supplier orders
    """
    service = OrderService(db)

    order_details = service.get_order_with_details(order_id)

    if not order_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found"
        )

    return order_details


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_data: OrderStatusUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Update order status.

    Args:
        order_id: Order ID
        status_data: Status update data

    Returns:
        Updated order
    """
    service = OrderService(db)

    # Parse status enum
    try:
        new_status = OrderStatus(status_data.status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {status_data.status}",
        )

    order = service.update_order_status(order_id, new_status)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found"
        )

    if new_status == OrderStatus.DELIVERED:
        try:
            is_upgrade = any(
                item.product and item.product.delivery_type == DeliveryType.UPGRADE
                for item in order.items
            )
            if is_upgrade:
                from src.dashboard.routers.notifications import get_bot_instance
                from src.database.services.user_preference_service import UserPreferenceService
                from src.i18n.bot_translations import get_translation

                bot = get_bot_instance()
                if bot:
                    try:
                        language = UserPreferenceService(db).get_user_language(order.user_id)
                    except Exception:
                        language = "vi"
                    await bot.send_message(
                        chat_id=order.user_id,
                        text=get_translation(
                            "upgrade.done_customer_message",
                            language,
                            order_id=order.id,
                        ),
                    )
        except Exception as e:
            logger.warning(
                f"Failed to send upgrade done notification for order {order_id}: {e}"
            )

    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status.value,
        "total_amount": order.total_amount,
        "payment_transaction_id": order.payment_transaction_id,
        "created_at": to_utc_iso(order.created_at),
        "updated_at": to_utc_iso(order.updated_at),
    }
