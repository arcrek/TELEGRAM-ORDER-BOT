"""
Balances router — admin management of user wallet balances.
"""

import csv
import io
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.models.admin import Admin
from src.database.models.bot_user import BotUser
from src.database.services.balance_service import BalanceService
from src.database.services.bot_user_service import BotUserService
from src.database.services.topup_service import TopupService

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class BalanceUserRow(BaseModel):
    """Single user row returned in the paginated list."""

    bot_user_id: str
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    balance: int
    total_topup: int
    last_topup_at: str | None  # ISO string from service
    api_token: str | None = None


class BalanceTxRow(BaseModel):
    """Single balance transaction row."""

    id: str
    amount: int
    balance_after: int
    kind: str
    reference_id: str | None
    admin_id: str | None
    admin_username: str | None
    reason: str | None
    created_at: datetime


class TopupRow(BaseModel):
    """Single topup order row."""

    id: str
    amount: int
    status: str
    payment_provider: str | None
    payment_transaction_id: str | None
    created_at: datetime
    updated_at: datetime


class BalanceUserDetail(BaseModel):
    """Detail view for a single user."""

    user: BalanceUserRow
    transactions: list[BalanceTxRow]
    transactions_total: int
    topups: list[TopupRow]
    topups_total: int


class BalanceAdjustRequest(BaseModel):
    """Admin balance adjustment request."""

    action: Literal["add", "subtract", "set"]
    amount: int = Field(ge=0)
    reason: str | None = None


class BalanceAdjustResponse(BaseModel):
    """Admin balance adjustment response."""

    success: bool
    new_balance: int
    reason: str | None = None  # error code when success=False


class ApiTokenResponse(BaseModel):
    """Response after generating or revoking an API token."""

    bot_user_id: str
    api_token: str | None  # None after revocation


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_balances(
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    sort_by: str = Query("balance"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_admin=Depends(require_viewer_or_admin),
):
    """
    Paginated list of all bot users with their balance and topup statistics.
    """
    items, total = BalanceService(db).list_users_with_balance(
        search=search,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/export")
async def export_active_users(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    """Export active, started bot users to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Name", "Telegram ID", "Balance"])
    for user in BotUserService(db).get_active_users():
        writer.writerow(
            [
                user.username or "",
                " ".join(filter(None, [user.first_name, user.last_name])),
                user.telegram_user_id,
                user.balance,
            ]
        )

    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=active_users_export.csv"
        },
    )


@router.get("/{bot_user_id}", response_model=BalanceUserDetail)
async def get_balance_detail(
    bot_user_id: str,
    transactions_page: int = Query(1, ge=1),
    transactions_per_page: int = Query(25, ge=1, le=100),
    topups_page: int = Query(1, ge=1),
    topups_per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin=Depends(require_viewer_or_admin),
):
    """
    Detailed view of a single user's balance, transaction history, and topup orders.
    """
    balance_svc = BalanceService(db)
    topup_svc = TopupService(db)

    # Fetch user summary.
    user_summary = balance_svc.get_user_summary(bot_user_id)
    if user_summary is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch paginated transaction history.
    txns, txns_total = balance_svc.get_user_history(
        bot_user_id,
        page=transactions_page,
        per_page=transactions_per_page,
    )

    # Resolve admin usernames for audit rows.
    admin_ids = {t.admin_id for t in txns if t.admin_id is not None}
    admin_map: dict[str, str] = {}
    if admin_ids:
        admins = db.query(Admin).filter(Admin.id.in_(admin_ids)).all()
        admin_map = {a.id: a.username for a in admins}

    tx_rows = [
        BalanceTxRow(
            id=t.id,
            amount=t.amount,
            balance_after=t.balance_after,
            kind=t.kind.value if hasattr(t.kind, "value") else str(t.kind),
            reference_id=t.reference_id,
            admin_id=t.admin_id,
            admin_username=admin_map.get(t.admin_id) if t.admin_id else None,
            reason=t.reason,
            created_at=t.created_at,
        )
        for t in txns
    ]

    # Fetch paginated topup orders.
    topups, topups_total = topup_svc.list_user_topups(
        bot_user_id,
        page=topups_page,
        per_page=topups_per_page,
    )

    topup_rows = [
        TopupRow(
            id=tp.id,
            amount=tp.amount,
            status=tp.status.value if hasattr(tp.status, "value") else str(tp.status),
            payment_provider=tp.payment_provider,
            payment_transaction_id=tp.payment_transaction_id,
            created_at=tp.created_at,
            updated_at=tp.updated_at,
        )
        for tp in topups
    ]

    return BalanceUserDetail(
        user=BalanceUserRow(**user_summary),
        transactions=tx_rows,
        transactions_total=txns_total,
        topups=topup_rows,
        topups_total=topups_total,
    )


@router.post("/{bot_user_id}/adjust", response_model=BalanceAdjustResponse)
async def adjust_balance(
    bot_user_id: str,
    payload: BalanceAdjustRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    """
    Admin: add, subtract, or set a user's balance.
    Requires admin role. Creates an audit BalanceTransaction record.
    """
    success, code, new_balance = BalanceService(db).adjust(
        bot_user_id=bot_user_id,
        action=payload.action,
        amount=payload.amount,
        admin_id=current_admin.id,
        reason=payload.reason,
    )
    if not success:
        if code == "not_found":
            raise HTTPException(status_code=404, detail="User not found")
        if code == "insufficient":
            raise HTTPException(
                status_code=400, detail="Insufficient balance for subtraction"
            )
        if code == "invalid_amount":
            raise HTTPException(status_code=400, detail="Invalid amount")
        if code == "invalid_action":
            raise HTTPException(status_code=400, detail="Invalid action")
        raise HTTPException(status_code=400, detail=code)
    return BalanceAdjustResponse(success=True, new_balance=new_balance)


@router.post("/{bot_user_id}/api-token", response_model=ApiTokenResponse)
async def generate_api_token(
    bot_user_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    """
    Admin: generate (or regenerate) an API token for a bot user.
    The token is stored in plaintext so the dashboard can display it.
    Calling this endpoint again replaces the existing token.
    """
    # Resolve telegram_user_id from bot_user_id (UUID primary key)
    bot_user = db.query(BotUser).filter_by(id=bot_user_id).first()
    if not bot_user:
        raise HTTPException(status_code=404, detail="User not found")

    token = BotUserService(db).generate_api_token(bot_user.telegram_user_id)
    if token is None:
        raise HTTPException(status_code=404, detail="User not found")

    return ApiTokenResponse(bot_user_id=bot_user_id, api_token=token)


@router.delete("/{bot_user_id}/api-token", response_model=ApiTokenResponse)
async def revoke_api_token(
    bot_user_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    """
    Admin: revoke (delete) the API token for a bot user.
    After this, any existing Bearer token for this user returns 401.
    """
    bot_user = db.query(BotUser).filter_by(id=bot_user_id).first()
    if not bot_user:
        raise HTTPException(status_code=404, detail="User not found")

    revoked = BotUserService(db).revoke_api_token(bot_user.telegram_user_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="User not found")

    return ApiTokenResponse(bot_user_id=bot_user_id, api_token=None)
