"""Blocked-user model — a row's existence blocks a Telegram id or username."""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Index, text
from sqlalchemy.sql import func
from src.database.models.base import Base


class BlockedUser(Base):
    """A single block entry, keyed by either a Telegram id OR a username."""

    __tablename__ = "blocked_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_blocked_users_telegram_user_id",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("telegram_user_id IS NOT NULL"),
            sqlite_where=text("telegram_user_id IS NOT NULL"),
        ),
        Index(
            "ix_blocked_users_username",
            "username",
            unique=True,
            postgresql_where=text("username IS NOT NULL"),
            sqlite_where=text("username IS NOT NULL"),
        ),
    )
