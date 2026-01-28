"""
Notification settings model for global order notification configuration.
"""
import uuid
from sqlalchemy import Column, String, Boolean, Text, DateTime
from sqlalchemy.sql import func
from src.database.models.base import Base


class NotificationSettings(Base):
    """Singleton-style settings row for order notifications."""

    __tablename__ = "notification_settings"

    # We keep a generic string ID to allow future multiple profiles if needed.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Master toggle
    order_notify_enabled = Column(Boolean, nullable=False, default=False)

    # Event toggles
    order_notify_on_created = Column(Boolean, nullable=False, default=False)
    order_notify_on_paid = Column(Boolean, nullable=False, default=False)

    # JSON-encoded list of Telegram chat IDs (can be user or group IDs)
    order_notify_whitelist_chat_ids = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

