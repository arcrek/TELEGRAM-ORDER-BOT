"""
User preference model for storing user settings like language.
"""
import uuid
from sqlalchemy import Column, String, BigInteger, DateTime
from sqlalchemy.sql import func
from src.database.models.base import Base


class UserPreference(Base):
    """User preference model for Telegram users."""

    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    language = Column(String, default="en", nullable=False)  # 'en' or 'vi'
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

