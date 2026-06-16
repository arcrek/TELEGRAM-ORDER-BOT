"""
Balance service — atomic wallet operations for the stored-value balance feature.

All balance mutations use atomic conditional UPDATE statements (no read-then-write).
Both the order/topup status transition and the balance change happen inside a single
transaction so they either both succeed or both roll back.
"""

from typing import Optional
from uuid import uuid4

from sqlalchemy import update, select, func
from sqlalchemy.orm import Session

from src.database.models import (
    BotUser,
    Order,
    BalanceTransaction,
)
from src.database.models.enums import OrderStatus, BalanceTxKind


class BalanceService:
    """Service for atomic balance operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Mutation methods (all atomic)
    # ------------------------------------------------------------------

    def pay_order_with_balance(
        self, order_id: str, bot_user: BotUser
    ) -> tuple[bool, str]:
        """
        Atomically transition order PENDING -> PAID and deduct balance.

        Both atomic checks run in the same transaction; rollback covers both.

        Returns:
            (success, reason) where reason is one of:
            'ok' | 'not_found' | 'already_processed' | 'insufficient'
        """
        # Validate order belongs to this user (non-atomic pre-check is fine — if
        # the order doesn't exist or belongs to someone else we return not_found
        # without touching any balance).
        order = self.session.execute(
            select(Order).where(Order.id == order_id)
        ).scalar_one_or_none()
        if order is None or order.user_id != bot_user.telegram_user_id:
            return False, "not_found"

        amount = order.total_amount
        tx_id = f"BAL-{uuid4().hex[:12]}"

        # 1) Atomic order status transition — prevents double-pay of same order.
        r1 = self.session.execute(
            update(Order)
            .where(Order.id == order_id, Order.status == OrderStatus.PENDING)
            .values(
                status=OrderStatus.PAID,
                payment_provider="balance",
                payment_transaction_id=tx_id,
            )
        )
        if r1.rowcount == 0:
            return False, "already_processed"

        # 2) Atomic balance deduction — prevents negative balance under contention.
        r2 = self.session.execute(
            update(BotUser)
            .where(BotUser.id == bot_user.id, BotUser.balance >= amount)
            .values(balance=BotUser.balance - amount)
        )
        if r2.rowcount == 0:
            self.session.rollback()  # rolls back the Order transition too
            return False, "insufficient"

        # 3) Read the committed new balance for the audit row.
        new_balance: int = self.session.execute(
            select(BotUser.balance).where(BotUser.id == bot_user.id)
        ).scalar_one()

        # 4) Append audit record.
        self.session.add(
            BalanceTransaction(
                bot_user_id=bot_user.id,
                amount=-amount,
                balance_after=new_balance,
                kind=BalanceTxKind.ORDER_PAYMENT,
                reference_id=order_id,
            )
        )
        self.session.commit()
        return True, "ok"

    def refund_order(
        self, order_id: str, refund_amount: int, telegram_admin_id: int
    ) -> tuple[bool, str]:
        """
        Atomically mark order REFUNDED and credit buyer's balance.

        The guard UPDATE ensures this is idempotent — a second call on a
        REFUNDED order returns (False, 'ineligible').

        Args:
            order_id: Order.id (string).
            refund_amount: Amount to credit (VND). Must be > 0.
            telegram_admin_id: Telegram user ID of the admin issuing the refund.

        Returns:
            (success, reason) where reason is one of:
            'ok' | 'not_found' | 'ineligible' | 'user_not_found'
        """
        # 1. Fetch the order so we can get user_id and validate existence.
        order = self.session.execute(
            select(Order).where(Order.id == order_id)
        ).scalar_one_or_none()
        if order is None:
            return False, "not_found"

        # 2. Atomic guard: only PAID / PROCESSING / DELIVERED are eligible.
        eligible = (OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.DELIVERED)
        r1 = self.session.execute(
            update(Order)
            .where(Order.id == order_id, Order.status.in_(eligible))
            .values(
                status=OrderStatus.REFUNDED,
                refunded_at=func.now(),
            )
        )
        if r1.rowcount == 0:
            return False, "ineligible"

        # 3. Look up BotUser by telegram_user_id.
        bot_user = self.session.execute(
            select(BotUser).where(BotUser.telegram_user_id == order.user_id)
        ).scalar_one_or_none()
        if bot_user is None:
            self.session.rollback()
            return False, "user_not_found"

        # 4. Credit balance (atomic addition cannot fail).
        self.session.execute(
            update(BotUser)
            .where(BotUser.id == bot_user.id)
            .values(balance=BotUser.balance + refund_amount)
        )

        # 5. Read back the new balance for the audit row.
        new_balance: int = self.session.execute(
            select(BotUser.balance).where(BotUser.id == bot_user.id)
        ).scalar_one()

        # 6. Append audit record.
        self.session.add(
            BalanceTransaction(
                bot_user_id=bot_user.id,
                amount=refund_amount,
                balance_after=new_balance,
                kind=BalanceTxKind.REFUND,
                reference_id=order_id,
                admin_id=None,
                reason=f"Refund via /rf by tg:{telegram_admin_id}",
            )
        )
        self.session.commit()
        return True, "ok"

    def credit_topup(self, topup_id: str, transaction_id: str) -> tuple[bool, str]:
        """
        Atomically transition topup PENDING -> PAID and credit balance.

        Idempotent — calling twice on the same topup returns 'already_processed'
        the second time.

        Returns:
            (success, reason) where reason is one of:
            'ok' | 'not_found' | 'already_processed'
        """
        from src.database.models.topup_order import TopupOrder
        from src.database.models.enums import TopupStatus

        # SELECT first to get bot_user_id and amount (needed after UPDATE).
        topup = self.session.execute(
            select(TopupOrder).where(TopupOrder.id == topup_id)
        ).scalar_one_or_none()
        if topup is None:
            return False, "not_found"

        # Atomic transition PENDING -> PAID.
        r1 = self.session.execute(
            update(TopupOrder)
            .where(
                TopupOrder.id == topup_id,
                TopupOrder.status == TopupStatus.PENDING,
            )
            .values(
                status=TopupStatus.PAID,
                payment_transaction_id=transaction_id,
            )
        )
        if r1.rowcount == 0:
            # Already PAID or CANCELLED — distinguish for the caller.
            return False, "already_processed"

        # Atomic balance credit (addition cannot fail).
        self.session.execute(
            update(BotUser)
            .where(BotUser.id == topup.bot_user_id)
            .values(balance=BotUser.balance + topup.amount)
        )

        # Read back the new balance for the audit row.
        new_balance: int = self.session.execute(
            select(BotUser.balance).where(BotUser.id == topup.bot_user_id)
        ).scalar_one()

        self.session.add(
            BalanceTransaction(
                bot_user_id=topup.bot_user_id,
                amount=topup.amount,
                balance_after=new_balance,
                kind=BalanceTxKind.TOPUP,
                reference_id=topup_id,
            )
        )
        self.session.commit()
        return True, "ok"

    def adjust(
        self,
        bot_user_id: str,
        action: str,
        amount: int,
        admin_id: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, str, int]:
        """
        Admin balance adjustment.

        Args:
            bot_user_id: BotUser.id (not telegram_user_id)
            action: 'add' | 'subtract' | 'set'
            amount: The amount to add/subtract/set (>= 0 for 'set'; > 0 for others)
            admin_id: Admin.id that authorised the change
            reason: Optional admin-supplied note

        Returns:
            (success, reason_code, new_balance) where reason_code is:
            'ok' | 'not_found' | 'insufficient' | 'invalid_amount' | 'invalid_action'
            new_balance is 0 on failure.
        """
        # Validate action.
        if action not in ("add", "subtract", "set"):
            return False, "invalid_action", 0

        # Validate amount.
        if action == "set" and amount < 0:
            return False, "invalid_amount", 0
        if action in ("add", "subtract") and amount <= 0:
            return False, "invalid_amount", 0

        if action == "add":
            r = self.session.execute(
                update(BotUser)
                .where(BotUser.id == bot_user_id)
                .values(balance=BotUser.balance + amount)
            )
            if r.rowcount == 0:
                return False, "not_found", 0

            new_balance: int = self.session.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            signed_amount = amount
            kind = BalanceTxKind.ADMIN_ADD

        elif action == "subtract":
            r = self.session.execute(
                update(BotUser)
                .where(BotUser.id == bot_user_id, BotUser.balance >= amount)
                .values(balance=BotUser.balance - amount)
            )
            if r.rowcount == 0:
                # Distinguish not_found vs insufficient.
                exists = self.session.execute(
                    select(BotUser.id).where(BotUser.id == bot_user_id)
                ).scalar_one_or_none()
                if exists is None:
                    return False, "not_found", 0
                return False, "insufficient", 0

            new_balance = self.session.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            signed_amount = -amount
            kind = BalanceTxKind.ADMIN_SUBTRACT

        else:  # set
            # Read current balance first (same transaction) so we can compute delta.
            old_balance = self.session.execute(
                select(BotUser.balance)
                .where(BotUser.id == bot_user_id)
                .with_for_update()  # no-op on SQLite, useful row-lock on Postgres
            ).scalar_one_or_none()
            if old_balance is None:
                return False, "not_found", 0

            self.session.execute(
                update(BotUser).where(BotUser.id == bot_user_id).values(balance=amount)
            )
            new_balance = amount
            signed_amount = amount - old_balance
            kind = BalanceTxKind.ADMIN_SET

        self.session.add(
            BalanceTransaction(
                bot_user_id=bot_user_id,
                amount=signed_amount,
                balance_after=new_balance,
                kind=kind,
                admin_id=admin_id,
                reason=reason,
            )
        )
        self.session.commit()
        return True, "ok", new_balance

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_balance(self, bot_user_id: str) -> int:
        """Return the current balance for a BotUser (0 if not found)."""
        result = self.session.execute(
            select(BotUser.balance).where(BotUser.id == bot_user_id)
        ).scalar_one_or_none()
        return result if result is not None else 0

    def list_users_with_balance(
        self,
        *,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 15,
        sort_by: str = "balance",
        sort_order: str = "desc",
    ) -> tuple[list[dict], int]:
        """
        Paginated list of users with their balance statistics.

        Returns:
            (items, total) where each item is a dict with keys:
            bot_user_id, telegram_user_id, username, first_name, last_name,
            balance, total_topup, last_topup_at.
        """
        from src.database.models.topup_order import TopupOrder
        from src.database.models.enums import TopupStatus
        from sqlalchemy import case

        # Subquery: per-user topup aggregates (PAID only).
        topup_sub = (
            self.session.query(
                TopupOrder.bot_user_id.label("bot_user_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (TopupOrder.status == TopupStatus.PAID, TopupOrder.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_topup"),
                func.max(
                    case(
                        (TopupOrder.status == TopupStatus.PAID, TopupOrder.created_at),
                        else_=None,
                    )
                ).label("last_topup_at"),
            )
            .group_by(TopupOrder.bot_user_id)
            .subquery()
        )

        # Main query joining BotUser with topup aggregates.
        query = self.session.query(
            BotUser,
            func.coalesce(topup_sub.c.total_topup, 0).label("total_topup"),
            topup_sub.c.last_topup_at,
        ).outerjoin(topup_sub, BotUser.id == topup_sub.c.bot_user_id)

        # Search filter.
        if search:
            pattern = f"%{search}%"
            from sqlalchemy import or_, cast
            from sqlalchemy import String as SAString

            query = query.filter(
                or_(
                    BotUser.username.ilike(pattern),
                    BotUser.first_name.ilike(pattern),
                    BotUser.last_name.ilike(pattern),
                    cast(BotUser.telegram_user_id, SAString).ilike(pattern),
                )
            )

        # Total count (before pagination).
        total: int = query.count()

        # Sort.
        desc_order = sort_order.lower() == "desc"
        if sort_by == "balance":
            order_col = BotUser.balance.desc() if desc_order else BotUser.balance.asc()
        elif sort_by == "total_topup":
            order_col = (
                func.coalesce(topup_sub.c.total_topup, 0).desc()
                if desc_order
                else func.coalesce(topup_sub.c.total_topup, 0).asc()
            )
        else:  # updated_at / default
            order_col = (
                BotUser.updated_at.desc() if desc_order else BotUser.updated_at.asc()
            )

        query = query.order_by(order_col)

        # Pagination.
        offset = (page - 1) * per_page
        rows = query.offset(offset).limit(per_page).all()

        items = [
            {
                "bot_user_id": user.id,
                "telegram_user_id": user.telegram_user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "balance": user.balance,
                "total_topup": total_topup,
                "last_topup_at": last_topup_at.isoformat() if last_topup_at else None,
                "api_token": user.api_token,
            }
            for user, total_topup, last_topup_at in rows
        ]
        return items, total

    def get_user_summary(self, bot_user_id: str) -> Optional[dict]:
        """
        Return balance summary dict for a single user, or None if not found.
        Dict keys: bot_user_id, telegram_user_id, username, first_name, last_name,
        balance, total_topup, last_topup_at (ISO string or None).
        """
        from src.database.models.topup_order import TopupOrder
        from src.database.models.enums import TopupStatus
        from sqlalchemy import case

        user = self.session.execute(
            select(BotUser).where(BotUser.id == bot_user_id)
        ).scalar_one_or_none()
        if user is None:
            return None

        topup_agg = (
            self.session.query(
                func.coalesce(
                    func.sum(
                        case(
                            (TopupOrder.status == TopupStatus.PAID, TopupOrder.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_topup"),
                func.max(
                    case(
                        (TopupOrder.status == TopupStatus.PAID, TopupOrder.created_at),
                        else_=None,
                    )
                ).label("last_topup_at"),
            )
            .filter(TopupOrder.bot_user_id == bot_user_id)
            .one()
        )

        return {
            "bot_user_id": user.id,
            "telegram_user_id": user.telegram_user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "balance": user.balance,
            "total_topup": topup_agg.total_topup or 0,
            "last_topup_at": topup_agg.last_topup_at.isoformat()
            if topup_agg.last_topup_at
            else None,
            "api_token": user.api_token,
        }

    def get_user_history(
        self,
        bot_user_id: str,
        *,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[BalanceTransaction], int]:
        """
        Paginated BalanceTransaction history for a user (newest first).

        Returns:
            (transactions, total)
        """
        base = self.session.query(BalanceTransaction).filter(
            BalanceTransaction.bot_user_id == bot_user_id
        )
        total: int = base.count()
        txns = (
            base.order_by(BalanceTransaction.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return txns, total
