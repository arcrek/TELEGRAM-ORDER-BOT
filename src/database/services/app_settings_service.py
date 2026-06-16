"""
Service layer for global application settings (singleton).
"""

import logging
import os
from sqlalchemy.orm import Session
from src.database.models.app_settings import AppSettings
from src.utils.datetime_format import validate_timezone

logger = logging.getLogger(__name__)

_DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
_SINGLETON_ID = "global"


class AppSettingsService:
    """Service for managing global application settings."""

    def __init__(self, session: Session):
        self.session = session

    def get_settings(self) -> AppSettings:
        """Return the singleton settings row, creating it on first access.

        The initial timezone is seeded from the APP_TIMEZONE environment
        variable (fallback: Asia/Ho_Chi_Minh).
        """
        settings = self.session.query(AppSettings).filter_by(id=_SINGLETON_ID).first()
        if settings:
            return settings

        seed_tz = os.getenv("APP_TIMEZONE", _DEFAULT_TIMEZONE)
        if not validate_timezone(seed_tz):
            logger.warning(
                "APP_TIMEZONE=%r is not a valid IANA timezone; defaulting to %s",
                seed_tz,
                _DEFAULT_TIMEZONE,
            )
            seed_tz = _DEFAULT_TIMEZONE

        settings = AppSettings(
            id=_SINGLETON_ID,
            timezone=seed_tz,
        )
        self.session.add(settings)
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def update_settings(self, *, timezone: str) -> AppSettings:
        """Update the global timezone.

        Raises:
            ValueError: if timezone is not a valid IANA name.
        """
        if not validate_timezone(timezone):
            raise ValueError(f"Invalid IANA timezone: {timezone!r}")

        settings = self.get_settings()
        settings.timezone = timezone
        self.session.commit()
        self.session.refresh(settings)
        return settings
