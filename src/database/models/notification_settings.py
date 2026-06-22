"""
Notification settings model for global order notification configuration.
"""
import uuid
from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer
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
    topup_notify_on_paid = Column(Boolean, nullable=False, default=False, server_default="false")

    # JSON-encoded list of Telegram chat IDs (can be user or group IDs)
    order_notify_whitelist_chat_ids = Column(Text, nullable=True)

    # Separate JSON-encoded list for UPGRADE account-info forwarding + Done button.
    # When empty, _handle_customer_reply falls back to order_notify_whitelist_chat_ids.
    upgrade_notify_chat_ids = Column(Text, nullable=True)

    # Separate JSON-encoded list for BALANCE_TOPUP_PAID notifications.
    # When empty, _send_topup_async falls back to order_notify_whitelist_chat_ids.
    topup_notify_chat_ids = Column(Text, nullable=True)

    # FK-by-convention (no DB constraint) to emoji_placeholders.id for the
    # notification header/footer. Null = none. Dangling id renders to empty.
    header_placeholder_id = Column(Integer, nullable=True)
    footer_placeholder_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

