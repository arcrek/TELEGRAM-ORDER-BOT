"""
Bot user model for tracking Telegram users.
"""

import uuid

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from src.database.models.base import Base


class BotUser(Base):
    """Bot user model for tracking Telegram users."""

    __tablename__ = "bot_users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    has_started = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    balance = Column(BigInteger, nullable=False, default=0, server_default="0")
    api_token = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
