"""Refunds router — user-based prorated refund calculator for the dashboard.

Admin-facing strings are Vietnamese (consistent with admin-only flows).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_viewer_or_admin
from src.database.models.admin import Admin
from src.database.models.enums import OrderStatus
from src.database.services.bot_user_service import BotUserService
from src.database.services.order_service import OrderService
from src.utils.datetime_format import to_utc_iso

router = APIRouter()

_ELIGIBLE = {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.DELIVERED}

_INELIGIBLE_REASON = {
    OrderStatus.PENDING: "Chưa thanh toán",
    OrderStatus.CANCELLED: "Đã huỷ",
    OrderStatus.REFUNDED: "Đã hoàn tiền",
}


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RefundOrderItem(BaseModel):
    product: Optional[str]
    variation: Optional[str]
    quantity: int


class RefundOrderRow(BaseModel):
    id: str
    status: str
    total_amount: int
    created_at: Optional[str]
    items: list[RefundOrderItem]
    eligible: bool
    ineligible_reason: Optional[str]


class RefundUser(BaseModel):
    telegram_user_id: int
    username: Optional[str]
    name: Optional[str]
    balance: int


class RefundOrdersResponse(BaseModel):
    user: RefundUser
    orders: list[RefundOrderRow]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _resolve_user(db: Session, search: str):
    """Resolve a BotUser by telegram id (all-digits) or username (else)."""
    s = (search or "").strip()
    if not s:
        return None
    svc = BotUserService(db)
    if s.isdigit():
        return svc.get_user_by_telegram_id(int(s))
    return svc.get_user_by_username(s)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/orders", response_model=RefundOrdersResponse)
async def list_user_orders(
    search: str = Query(..., min_length=1),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_viewer_or_admin),
):
    user = _resolve_user(db, search)
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    orders = OrderService(db).list_orders(
        user_id=user.telegram_user_id,
        start_date=start_date,
        end_date=end_date,
        page=1,
        per_page=1000,
    )

    rows: list[RefundOrderRow] = []
    for o in orders:
        eligible = o.status in _ELIGIBLE
        items = [
            RefundOrderItem(
                product=(it.product.name if it.product else None),
                variation=(it.variation.name if it.variation else None),
                quantity=it.quantity,
            )
            for it in o.items
        ]
        rows.append(
            RefundOrderRow(
                id=o.id,
                status=o.status.value,
                total_amount=o.total_amount,
                created_at=to_utc_iso(o.created_at),
                items=items,
                eligible=eligible,
                ineligible_reason=(
                    None
                    if eligible
                    else _INELIGIBLE_REASON.get(o.status, "Không đủ điều kiện")
                ),
            )
        )

    name = " ".join(p for p in [user.first_name, user.last_name] if p) or None
    return RefundOrdersResponse(
        user=RefundUser(
            telegram_user_id=user.telegram_user_id,
            username=user.username,
            name=name,
            balance=user.balance or 0,
        ),
        orders=rows,
    )
