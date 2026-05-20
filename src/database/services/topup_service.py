"""
Topup service — CRUD operations on TopupOrder.
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import update, select
from sqlalchemy.orm import Session

from src.database.models.topup_order import TopupOrder
from src.database.models.bot_user import BotUser
from src.database.models.enums import TopupStatus

# Topup amount bounds (VND)
BALANCE_TOPUP_MIN = 10_000
BALANCE_TOPUP_MAX = 50_000_000


class TopupService:
    """Service for managing TopupOrder records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    def generate_topup_id(self) -> str:
        """
        Return 'TU' + 8-char lowercase hex, unique within topup_orders.
        Retries on collision (astronomically unlikely with 16^8 = 4 billion space).
        """
        for _ in range(30):
            candidate = "TU" + secrets.token_hex(4)
            exists = self.session.execute(
                select(TopupOrder.id).where(TopupOrder.id == candidate)
            ).scalar_one_or_none()
            if exists is None:
                return candidate
        raise RuntimeError("Unable to generate unique TopupOrder ID after retries")

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create_topup(self, *, bot_user: BotUser, amount: int) -> TopupOrder:
        """
        Create a PENDING TopupOrder for the given user.

        Args:
            bot_user: The BotUser making the top-up request.
            amount:   Amount in VND; must be within [BALANCE_TOPUP_MIN, BALANCE_TOPUP_MAX].

        Returns:
            Newly created TopupOrder instance.

        Raises:
            ValueError: If amount is out of bounds.
        """
        if amount < BALANCE_TOPUP_MIN or amount > BALANCE_TOPUP_MAX:
            raise ValueError(
                f"Topup amount {amount} is out of bounds "
                f"[{BALANCE_TOPUP_MIN}, {BALANCE_TOPUP_MAX}]"
            )

        topup_id = self.generate_topup_id()
        topup = TopupOrder(
            id=topup_id,
            user_id=bot_user.telegram_user_id,
            bot_user_id=bot_user.id,
            amount=amount,
            status=TopupStatus.PENDING,
        )
        self.session.add(topup)
        self.session.commit()
        self.session.refresh(topup)
        return topup

    def cancel_topup(self, topup_id: str) -> bool:
        """
        Atomically cancel a PENDING TopupOrder.

        Returns:
            True if the topup was cancelled; False if already PAID/CANCELLED.
        """
        r = self.session.execute(
            update(TopupOrder)
            .where(
                TopupOrder.id == topup_id,
                TopupOrder.status == TopupStatus.PENDING,
            )
            .values(status=TopupStatus.CANCELLED)
        )
        if r.rowcount == 0:
            return False
        self.session.commit()
        return True

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_by_id(self, topup_id: str) -> Optional[TopupOrder]:
        """Return a TopupOrder by its string ID, or None."""
        return self.session.execute(
            select(TopupOrder).where(TopupOrder.id == topup_id)
        ).scalar_one_or_none()

    def get_by_payos_code(self, payos_order_code: int) -> Optional[TopupOrder]:
        """Return a TopupOrder by its PayOS orderCode, or None."""
        return self.session.execute(
            select(TopupOrder).where(TopupOrder.payos_order_code == payos_order_code)
        ).scalar_one_or_none()

    def list_user_topups(
        self,
        bot_user_id: str,
        *,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[TopupOrder], int]:
        """
        Paginated list of TopupOrders for a user (newest first).

        Returns:
            (topups, total)
        """
        base = (
            self.session.query(TopupOrder)
            .filter(TopupOrder.bot_user_id == bot_user_id)
        )
        total: int = base.count()
        topups = (
            base.order_by(TopupOrder.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return topups, total

    def find_expired_pending_topups(self, minutes: int = 30) -> list[TopupOrder]:
        """
        Return all PENDING TopupOrders older than `minutes` minutes.

        Used by the auto-cancel scheduler to expire stale topup requests.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        # created_at is stored without tz info (server_default=func.now()), so
        # compare against naive UTC just as auto_cancel_service does for orders.
        cutoff_naive = cutoff.replace(tzinfo=None)
        return (
            self.session.query(TopupOrder)
            .filter(
                TopupOrder.status == TopupStatus.PENDING,
                TopupOrder.created_at < cutoff_naive,
            )
            .all()
        )
