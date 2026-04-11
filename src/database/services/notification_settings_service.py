"""
Service layer for global notification settings.
"""
import json
from typing import Any, Dict, List, Optional
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

    def _parse_whitelist_target(self, value: Any) -> Optional[Dict[str, Optional[int]]]:
        """
        Parse one whitelist target value.

        Supported formats:
        - chat_id
        - "chat_id"
        - "chat_id:message_thread_id"
        - {"chat_id": ..., "message_thread_id": ...}
        """
        if isinstance(value, dict):
            raw_chat_id = value.get("chat_id")
            raw_thread_id = value.get("message_thread_id")
        elif isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return None

            if ":" in raw_value:
                parts = raw_value.split(":", 1)
                raw_chat_id = parts[0].strip()
                raw_thread_id = parts[1].strip()
                if raw_thread_id == "":
                    return None
            else:
                raw_chat_id = raw_value
                raw_thread_id = None
        else:
            raw_chat_id = value
            raw_thread_id = None

        try:
            chat_id = int(raw_chat_id)
        except (TypeError, ValueError):
            return None

        message_thread_id: Optional[int] = None
        if raw_thread_id is not None:
            try:
                message_thread_id = int(raw_thread_id)
            except (TypeError, ValueError):
                return None
            if message_thread_id <= 0:
                return None

        return {
            "chat_id": chat_id,
            "message_thread_id": message_thread_id,
        }

    def _target_to_storage_value(self, target: Dict[str, Optional[int]]) -> str:
        """Convert parsed target to canonical string for storage."""
        chat_id = int(target["chat_id"])
        message_thread_id = target.get("message_thread_id")
        if message_thread_id is not None:
            return f"{chat_id}:{int(message_thread_id)}"
        return str(chat_id)

    def get_whitelist_targets(
        self, settings: Optional[NotificationSettings] = None
    ) -> List[Dict[str, Optional[int]]]:
        """
        Get parsed whitelist targets from settings.

        Args:
            settings: Optional NotificationSettings instance. If not provided,
                the singleton settings row is loaded.

        Returns:
            List of targets containing chat_id and optional message_thread_id.
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

        targets: List[Dict[str, Optional[int]]] = []
        seen = set()
        if isinstance(data, list):
            for value in data:
                parsed = self._parse_whitelist_target(value)
                if not parsed:
                    continue
                key = self._target_to_storage_value(parsed)
                if key in seen:
                    continue
                seen.add(key)
                targets.append(parsed)
        return targets

    def get_whitelist_chat_ids(
        self, settings: Optional[NotificationSettings] = None
    ) -> List[int]:
        """
        Backward-compatible view of whitelist targets as chat IDs only.
        """
        targets = self.get_whitelist_targets(settings)
        ids: List[int] = []
        seen = set()
        for target in targets:
            chat_id = int(target["chat_id"])
            if chat_id in seen:
                continue
            seen.add(chat_id)
            ids.append(chat_id)
        return ids

    def get_whitelist_entries(
        self, settings: Optional[NotificationSettings] = None
    ) -> List[str]:
        """
        Get whitelist in text entry format suitable for UI display/editing.
        """
        targets = self.get_whitelist_targets(settings)
        return [self._target_to_storage_value(target) for target in targets]

    def update_settings(
        self,
        *,
        order_notify_enabled: Optional[bool] = None,
        order_notify_on_created: Optional[bool] = None,
        order_notify_on_paid: Optional[bool] = None,
        whitelist_chat_ids: Optional[List[Any]] = None,
    ) -> NotificationSettings:
        """
        Update notification settings.

        All parameters are optional; only provided values are updated.

        Args:
            order_notify_enabled: Master toggle for order notifications.
            order_notify_on_created: Whether to notify when an order is created (PENDING).
            order_notify_on_paid: Whether to notify when an order is paid (PAID).
            whitelist_chat_ids: List of targets to notify.
                Supported values: `chat_id` or `chat_id:message_thread_id`.

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
            # Normalize to unique canonical string entries.
            normalized_entries: List[str] = []
            seen = set()
            for value in whitelist_chat_ids:
                parsed = self._parse_whitelist_target(value)
                if not parsed:
                    continue
                entry = self._target_to_storage_value(parsed)
                if entry not in seen:
                    seen.add(entry)
                    normalized_entries.append(entry)
            settings.order_notify_whitelist_chat_ids = json.dumps(normalized_entries)

        self.session.commit()
        self.session.refresh(settings)
        return settings

