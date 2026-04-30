"""
BotAdmin model — Telegram users with bot-admin privileges.

Separate from the dashboard Admin model (which tracks web-panel users with
passwords). BotAdmin stores only the Telegram user IDs that are allowed to
use bot-admin commands (/setadmin, /notify_*, upgrade Done button, etc.).
"""
from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.sql import func

from src.database.models.base import Base


class BotAdmin(Base):
    """Telegram user IDs with bot-admin privileges."""

    __tablename__ = "bot_admins"

    id = Column(String, primary_key=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    # Who added this admin (Telegram user ID of the super admin who ran /setadmin).
    added_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
