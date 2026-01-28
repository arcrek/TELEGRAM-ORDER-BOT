"""
Service layer for global notification settings.
"""
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from src.database.models.notification_settings import NotificationSettings


class NotificationSettingsService:
    """Service for managing global order notification settings."""

    _SINGLETON_ID = "global"

    def __init__(self, session: Session):
        """
        Initialize notification settings service.

        Args:
            session: Database session
        """
        self.session = session

    def get_settings(self) -> NotificationSettings:
        """
        Get the singleton notification settings row, creating it if missing.

        Returns:
            NotificationSettings instance
        """
        settings = (
            self.session.query(NotificationSettings)
            .filter_by(id=self._SINGLETON_ID)
            .first()
        )
        if settings:
            return settings

        settings = NotificationSettings(
            id=self._SINGLETON_ID,
            order_notify_enabled=False,
            order_notify_on_created=False,
            order_notify_on_paid=False,
            order_notify_whitelist_chat_ids=json.dumps([]),
        )
        self.session.add(settings)
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def get_whitelist_chat_ids(
        self, settings: Optional[NotificationSettings] = None
    ) -> List[int]:
        """
        Get parsed whitelist chat IDs from settings.

        Args:
            settings: Optional NotificationSettings instance. If not provided,
                the singleton settings row is loaded.

        Returns:
            List of Telegram chat IDs (can be user or group IDs).
        """
        if settings is None:
            settings = self.get_settings()

        raw = settings.order_notify_whitelist_chat_ids
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []

        ids: List[int] = []
        if isinstance(data, list):
            for value in data:
                try:
                    # Accept strings or numbers, skip invalid entries.
                    ids.append(int(value))
                except (TypeError, ValueError):
                    continue
        return ids

    def update_settings(
        self,
        *,
        order_notify_enabled: Optional[bool] = None,
        order_notify_on_created: Optional[bool] = None,
        order_notify_on_paid: Optional[bool] = None,
        whitelist_chat_ids: Optional[List[int]] = None,
    ) -> NotificationSettings:
        """
        Update notification settings.

        All parameters are optional; only provided values are updated.

        Args:
            order_notify_enabled: Master toggle for order notifications.
            order_notify_on_created: Whether to notify when an order is created (PENDING).
            order_notify_on_paid: Whether to notify when an order is paid (PAID).
            whitelist_chat_ids: List of Telegram chat IDs to notify.

        Returns:
            Updated NotificationSettings instance.
        """
        settings = self.get_settings()

        if order_notify_enabled is not None:
            settings.order_notify_enabled = bool(order_notify_enabled)
        if order_notify_on_created is not None:
            settings.order_notify_on_created = bool(order_notify_on_created)
        if order_notify_on_paid is not None:
            settings.order_notify_on_paid = bool(order_notify_on_paid)
        if whitelist_chat_ids is not None:
            # Normalize to unique ints.
            normalized_ids: List[int] = []
            seen = set()
            for value in whitelist_chat_ids:
                try:
                    chat_id = int(value)
                except (TypeError, ValueError):
                    continue
                if chat_id not in seen:
                    seen.add(chat_id)
                    normalized_ids.append(chat_id)
            settings.order_notify_whitelist_chat_ids = json.dumps(normalized_ids)

        self.session.commit()
        self.session.refresh(settings)
        return settings

