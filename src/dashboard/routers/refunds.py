"""Refunds router — user-based prorated refund calculator for the dashboard.

Admin-facing strings are Vietnamese (consistent with admin-only flows).
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.models.admin import Admin
from src.database.models.enums import OrderStatus
from src.database.services.balance_service import BalanceService
from src.database.services.bot_user_service import BotUserService
from src.database.services.order_service import OrderService
from src.utils.datetime_format import to_utc_iso
from src.utils.refund_calc import combine_duration, compute_refund

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


class PreviewItem(BaseModel):
    order_id: str
    days: int = 0
    months: int = 0
    years: int = 0


class PreviewRequest(BaseModel):
    items: list[PreviewItem]


class PreviewRow(BaseModel):
    order_id: str
    duration_days: int
    elapsed: int
    remaining: int
    daily_rate: int
    refund_amount: int
    eligible: bool


class PreviewResponse(BaseModel):
    rows: list[PreviewRow]
    total_refund: int


class ConfirmItem(BaseModel):
    order_id: str
    days: int = 0
    months: int = 0
    years: int = 0
    mode: Literal["credit", "status"]


class ConfirmRequest(BaseModel):
    items: list[ConfirmItem]


class ConfirmResult(BaseModel):
    order_id: str
    success: bool
    reason: str
    refund_amount: Optional[int] = None
    new_balance: Optional[int] = None


class ConfirmResponse(BaseModel):
    results: list[ConfirmResult]


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


@router.post("/preview", response_model=PreviewResponse)
async def preview_refunds(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_viewer_or_admin),
):
    order_service = OrderService(db)
    rows: list[PreviewRow] = []
    total = 0
    for item in payload.items:
        order = order_service.get_order_by_id(item.order_id)
        duration_days = combine_duration(item.days, item.months, item.years)
        if order is None:
            rows.append(PreviewRow(order_id=item.order_id, duration_days=duration_days,
                                   elapsed=0, remaining=0, daily_rate=0,
                                   refund_amount=0, eligible=False))
            continue
        eligible = order.status in _ELIGIBLE
        elapsed, remaining, refund = compute_refund(
            order.total_amount, duration_days, order.created_at
        )
        if not eligible:
            refund = 0
        daily_rate = round(order.total_amount / duration_days) if duration_days > 0 else 0
        total += refund
        rows.append(PreviewRow(order_id=item.order_id, duration_days=duration_days,
                               elapsed=elapsed, remaining=remaining,
                               daily_rate=daily_rate, refund_amount=refund,
                               eligible=eligible))
    return PreviewResponse(rows=rows, total_refund=total)


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_refunds(
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_admin_role),
):
    order_service = OrderService(db)
    balance_service = BalanceService(db)
    user_service = BotUserService(db)
    results: list[ConfirmResult] = []

    for item in payload.items:
        order = order_service.get_order_by_id(item.order_id)
        if order is None:
            results.append(ConfirmResult(order_id=item.order_id, success=False,
                                         reason="not_found"))
            continue

        if item.mode == "status":
            ok, reason = balance_service.mark_order_refunded(item.order_id)
            results.append(ConfirmResult(order_id=item.order_id, success=ok, reason=reason))
            continue

        # mode == "credit": recompute amount server-side.
        duration_days = combine_duration(item.days, item.months, item.years)
        _, _, refund = compute_refund(order.total_amount, duration_days, order.created_at)
        if refund <= 0:
            results.append(ConfirmResult(order_id=item.order_id, success=False,
                                         reason="no_refund", refund_amount=0))
            continue

        ok, reason = balance_service.refund_order(
            item.order_id, refund, admin_id=str(current_admin.id)
        )
        new_balance = None
        if ok:
            buyer = user_service.get_user_by_telegram_id(order.user_id)
            new_balance = buyer.balance if buyer else None
        results.append(ConfirmResult(
            order_id=item.order_id, success=ok, reason=reason,
            refund_amount=refund if ok else None, new_balance=new_balance,
        ))

    return ConfirmResponse(results=results)
