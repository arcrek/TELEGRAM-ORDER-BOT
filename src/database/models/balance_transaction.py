"""
Balance transaction model — append-only audit log of every balance change.
"""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, Enum, Index, String, Text
from sqlalchemy.sql import func

from src.database.models.base import Base
from src.database.models.enums import BalanceTxKind


class BalanceTransaction(Base):
    """Append-only audit log of every balance change for a bot user."""

    __tablename__ = "balance_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_user_id = Column(String, nullable=False, index=True)  # FK to bot_users.id
    amount = Column(BigInteger, nullable=False)  # Signed: + credit, - debit
    balance_after = Column(BigInteger, nullable=False)  # Snapshot of balance post-change

    kind = Column(
        Enum(BalanceTxKind, native_enum=False),
        nullable=False,
    )

    reference_id = Column(String, nullable=True)  # TopupOrder.id or Order.id
    admin_id = Column(String, nullable=True)  # FK to admins.id (for ADMIN_* kinds)
    reason = Column(Text, nullable=True)  # Admin-supplied note

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_balance_transactions_bot_user_created", "bot_user_id", "created_at"),
    )
