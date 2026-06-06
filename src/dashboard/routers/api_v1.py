"""
Public Order-via-API router.

Mounted at /api/v1 in the dashboard. All endpoints require a per-user
Bearer token issued to a BotUser. Payment is balance-only. Only
PRE_UPLOADED products are orderable via this API.

Pydantic schemas are defined inline at the top of this module per project
convention.
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.dashboard.api_auth import get_api_user
from src.dashboard.auth import get_db
from src.dashboard.limiter import limiter
from src.database.models.bot_user import BotUser
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.services.balance_service import BalanceService
from src.database.services.bonus_tier_service import BonusTierService
from src.database.services.discount_tier_service import DiscountTierService
from src.database.services.order_service import OrderService
from src.database.services.product_service import ProductService
from src.database.services.variation_service import VariationService

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Inline Pydantic schemas
# ---------------------------------------------------------------------------


class ApiVariationOut(BaseModel):
    """Variation summary returned in the product catalog."""

    id: str
    name: str
    price: int
    stock: int
    is_active: bool


class ApiProductOut(BaseModel):
    """Product summary returned in the catalog."""

    id: str
    name: str
    description: Optional[str]
    delivery_type: str
    is_active: bool
    variations: list[ApiVariationOut]


class ApiProductListOut(BaseModel):
    """Paginated product list response."""

    items: list[ApiProductOut]
    page: int
    per_page: int
    total: int
    note: str = (
        "Pages may contain fewer than per_page items because filtering to "
        "PRE_UPLOADED delivery type is applied after pagination."
    )


class ApiBalanceOut(BaseModel):
    """Current wallet balance for the authenticated user."""

    balance: int


class ApiOrderRequest(BaseModel):
    """Body for POST /orders."""

    variation_id: str
    quantity: int = Field(ge=1)


class ApiDeliveredProduct(BaseModel):
    """A single delivered pre-uploaded product row."""

    id: str
    used_at: Optional[str]
    display: str
    data: Optional[dict[str, Any]]


class ApiOrderItemOut(BaseModel):
    """One item in an order response."""

    id: str
    quantity: int
    bonus_quantity: int
    total_items: int
    unit_price: int
    subtotal: int
    discount_amount: int
    product_id: Optional[str]
    product_name: Optional[str]
    variation_id: Optional[str]
    variation_name: Optional[str]
    delivered_products: list[ApiDeliveredProduct]
    delivered_count: int


class ApiOrderOut(BaseModel):
    """Full order response."""

    id: str
    status: str
    total_amount: int
    discount_amount: int
    payment_transaction_id: Optional[str]
    created_at: str
    updated_at: str
    items: list[ApiOrderItemOut]


class ApiOrderSummaryOut(BaseModel):
    """Lightweight order summary for history list."""

    id: str
    status: str
    total_amount: int
    created_at: str


class ApiChargedUndeliveredError(BaseModel):
    """Returned (HTTP 502) when payment succeeded but delivery failed."""

    order_id: str
    status: str
    charged: bool = True
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_product_out(product, db: Session) -> Optional[ApiProductOut]:
    """Build ApiProductOut for a single product, or None if not PRE_UPLOADED."""
    if product.delivery_type != DeliveryType.PRE_UPLOADED:
        return None

    variation_svc = VariationService(db)
    raw_variations = variation_svc.list_variations_by_product(
        product.id, only_active=True
    )

    variations_out = [
        ApiVariationOut(
            id=v.id,
            name=v.name,
            price=v.price,
            stock=variation_svc.calculate_stock_from_pre_uploaded(v.id),
            is_active=v.is_active,
        )
        for v in raw_variations
    ]

    return ApiProductOut(
        id=product.id,
        name=product.name,
        description=product.description,
        delivery_type=product.delivery_type.value
        if hasattr(product.delivery_type, "value")
        else str(product.delivery_type),
        is_active=product.is_active,
        variations=variations_out,
    )


def _build_order_out(details: dict) -> ApiOrderOut:
    """Convert the dict returned by OrderService.get_order_with_details to ApiOrderOut."""
    items = []
    for item in details.get("items", []):
        delivered_raw = item.get("delivered_products", [])
        delivered = [
            ApiDeliveredProduct(
                id=d["id"],
                used_at=d.get("used_at"),
                display=d.get("display", ""),
                data=d.get("data"),
            )
            for d in delivered_raw
        ]
        items.append(
            ApiOrderItemOut(
                id=item["id"],
                quantity=item["quantity"],
                bonus_quantity=item.get("bonus_quantity", 0),
                total_items=item.get("total_items", item["quantity"]),
                unit_price=item["unit_price"],
                subtotal=item["subtotal"],
                discount_amount=item.get("discount_amount", 0),
                product_id=item.get("product_id"),
                product_name=item.get("product_name"),
                variation_id=item.get("variation_id"),
                variation_name=item.get("variation_name"),
                delivered_products=delivered,
                delivered_count=item.get("delivered_count", len(delivered)),
            )
        )

    return ApiOrderOut(
        id=details["id"],
        status=details["status"],
        total_amount=details["total_amount"],
        discount_amount=details.get("discount_amount", 0),
        payment_transaction_id=details.get("payment_transaction_id"),
        created_at=details["created_at"],
        updated_at=details["updated_at"],
        items=items,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/products", response_model=ApiProductListOut)
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: BotUser = Depends(get_api_user),
) -> ApiProductListOut:
    """
    List active PRE_UPLOADED products with per-variation stock.

    Note: page sizes may be smaller than per_page because PRE_UPLOADED
    filtering happens after pagination (v1 behaviour).
    """
    product_svc = ProductService(db)
    products = product_svc.list_products(
        page=page,
        per_page=per_page,
        only_active=True,
        search=search,
    )
    total = product_svc.get_total_count(only_active=True, search=search)

    items = []
    for product in products:
        out = _build_product_out(product, db)
        if out is not None:
            items.append(out)

    return ApiProductListOut(items=items, page=page, per_page=per_page, total=total)


@router.get("/products/{product_id}", response_model=ApiProductOut)
async def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: BotUser = Depends(get_api_user),
) -> ApiProductOut:
    """
    Get a single active PRE_UPLOADED product by ID.

    Returns 404 if the product does not exist, is inactive, or is not
    PRE_UPLOADED delivery type.
    """
    product_svc = ProductService(db)
    product = product_svc.get_product_by_id(product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    out = _build_product_out(product, db)
    if out is None:
        raise HTTPException(
            status_code=404, detail="Product not found or not available via API"
        )

    return out


@router.get("/balance", response_model=ApiBalanceOut)
async def get_balance(
    db: Session = Depends(get_db),
    current_user: BotUser = Depends(get_api_user),
) -> ApiBalanceOut:
    """Return the authenticated user's current wallet balance."""
    balance = BalanceService(db).get_balance(current_user.id)
    return ApiBalanceOut(balance=balance)


@router.post("/orders", status_code=200)
@limiter.limit("10/minute")
async def create_order(
    request: Request,
    payload: ApiOrderRequest,
    db: Session = Depends(get_db),
    current_user: BotUser = Depends(get_api_user),
):
    """
    Place a balance-paid order for a PRE_UPLOADED product variation.

    Rate-limited to 10 requests/minute per IP (enforced by slowapi).

    Steps:
    1. Validate variation is active and PRE_UPLOADED.
    2. Pre-check fulfillment bot availability (503 if bot is None).
    3. Resolve bonus/discount tiers (mirrors bot pricing logic).
    4. Create the order (409 on insufficient stock).
    5. Pay from balance (402 on insufficient; cancel reservation on failure).
    6. Fulfill via IPN processor.
    7. If delivery fails after payment: return 502 with charged=true.
    8. On success: return full order details including delivered content.
    """
    variation_id = payload.variation_id
    quantity = payload.quantity

    # 1. Load and validate variation + product
    variation_svc = VariationService(db)
    variation = variation_svc.get_variation_by_id(variation_id)
    if not variation or not variation.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Variation not found or inactive",
        )

    product_svc = ProductService(db)
    product = product_svc.get_product_by_id(variation.product_id)
    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product not found or inactive",
        )
    if product.delivery_type != DeliveryType.PRE_UPLOADED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Only PRE_UPLOADED products can be ordered via API. "
                f"This product has delivery_type '{product.delivery_type.value}'."
            ),
        )

    # 2. Pre-check bot availability (fulfillment will raise RuntimeError if bot is None)
    from src.ipn import get_ipn_processor

    processor = get_ipn_processor()
    if processor is None or processor.bot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Delivery service is temporarily unavailable. Please try again later."
            ),
        )

    # 3. Resolve pricing parity (mirrors callbacks.py:830-866)
    benefit_mode = getattr(variation, "benefit_mode", "bonus")
    actual_stock = variation_svc.calculate_stock_from_pre_uploaded(variation_id)

    bonus_quantity = 0
    if benefit_mode in ("bonus", "both"):
        bonus_svc = BonusTierService(db)
        bonus_tier = bonus_svc.get_applicable_bonus(
            variation_id, quantity, actual_stock
        )
        bonus_quantity = bonus_tier.bonus_quantity if bonus_tier else 0

    discount_tier = None
    if benefit_mode in ("discount", "both"):
        discount_svc = DiscountTierService(db)
        discount_tier = discount_svc.get_applicable_discount(variation_id, quantity)

    # 4. Create order
    order_svc = OrderService(db)
    try:
        order = order_svc.create_order(
            user_id=current_user.telegram_user_id,
            variation_id=variation_id,
            quantity=quantity,
            bonus_quantity=bonus_quantity,
            discount_tier=discount_tier,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    order_id = order.id

    # 5. Pay from balance
    balance_svc = BalanceService(db)
    success, reason = balance_svc.pay_order_with_balance(order_id, current_user)

    if not success:
        if reason == "insufficient":
            # Order is still PENDING — release the reservation immediately
            try:
                order_svc.cancel_order(order_id)
            except Exception as cancel_exc:
                logger.error(
                    "Failed to cancel order %s after insufficient balance: %s",
                    order_id,
                    cancel_exc,
                )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient wallet balance to complete this order.",
            )
        elif reason == "already_processed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order has already been processed.",
            )
        else:  # not_found or unknown
            logger.error(
                "Unexpected payment failure for order %s: %s", order_id, reason
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Payment failed unexpectedly: {reason}",
            )

    # 6. Fulfill via IPN processor (mirrors callbacks.py:1471-1485)
    delivery_ok = False
    delivery_error: Optional[Exception] = None
    try:
        loop = asyncio.get_running_loop()
        delivery_ok = await loop.run_in_executor(
            None,
            lambda: processor.process_balance_paid_order(
                order_id=order_id, request_loop=loop
            ),
        )
    except Exception as exc:
        delivery_error = exc
        logger.error(
            "Fulfillment raised an exception for balance-paid order %s: %s",
            order_id,
            exc,
            exc_info=True,
        )

    # 7. Re-read order state
    db.expire_all()
    details = order_svc.get_order_with_details(order_id)

    delivered_status = (details or {}).get("status", "")
    if (
        not delivery_ok
        or delivery_error
        or delivered_status != OrderStatus.DELIVERED.value
    ):
        # Payment is committed; inventory is consumed. Do NOT return a clean success.
        logger.error(
            "CHARGED-BUT-UNDELIVERED: order %s, delivery_ok=%s, status=%s, error=%s",
            order_id,
            delivery_ok,
            delivered_status,
            delivery_error,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "order_id": order_id,
                "status": delivered_status,
                "charged": True,
                "message": (
                    "Payment succeeded but delivery did not complete. "
                    "Contact support or check your order status."
                ),
            },
        )

    # 8. Return full order details
    return _build_order_out(details)


@router.get("/orders", response_model=list[ApiOrderSummaryOut])
async def list_orders(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: BotUser = Depends(get_api_user),
) -> list[ApiOrderSummaryOut]:
    """List order history for the authenticated user (newest first)."""
    order_svc = OrderService(db)
    orders = order_svc.get_user_orders(
        user_id=current_user.telegram_user_id,
        limit=limit,
    )
    return [
        ApiOrderSummaryOut(
            id=o.id,
            status=o.status.value if hasattr(o.status, "value") else str(o.status),
            total_amount=o.total_amount,
            created_at=o.created_at.isoformat(),
        )
        for o in orders
    ]


@router.get("/orders/{order_id}", response_model=ApiOrderOut)
async def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: BotUser = Depends(get_api_user),
) -> ApiOrderOut:
    """
    Retrieve a single order with full details including delivered content.

    Returns 404 if the order does not exist or belongs to a different user.
    """
    order_svc = OrderService(db)
    details = order_svc.get_order_with_details(order_id)

    if details is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Ownership check — 404 (not 403) to avoid information leakage
    if details.get("user_id") != current_user.telegram_user_id:
        raise HTTPException(status_code=404, detail="Order not found")

    return _build_order_out(details)
