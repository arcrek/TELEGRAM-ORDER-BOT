"""
Service layer for global application settings (singleton).
"""

import re
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from src.database.models.app_settings import AppSettings
from src.utils.datetime_format import validate_timezone

_SINGLETON_ID = "global"
_ORDER_PREFIX_RE = re.compile(r"^[A-Z0-9]{2,8}$")
_BOT_URL_RE = re.compile(r"^https://t\.me/[A-Za-z0-9_]{5,32}/?$")


def _https_url(name: str, value: str, *, required: bool) -> str:
    value = value.strip()
    if not value and not required:
        return ""
    if len(value) > 2048:
        raise ValueError(f"{name} must contain at most 2048 characters")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"{name} must be an absolute HTTPS URL")
    return value


class AppSettingsService:
    """Service for managing global application settings."""

    def __init__(self, session: Session):
        self.session = session

    def get_settings(self, commit: bool = True) -> AppSettings:
        """Return the singleton settings row, creating it on first access."""
        settings = self.session.query(AppSettings).filter_by(id=_SINGLETON_ID).first()
        if settings:
            return settings

        settings = AppSettings(id=_SINGLETON_ID)
        self.session.add(settings)
        if commit:
            self.session.commit()
            self.session.refresh(settings)
        else:
            self.session.flush()
        return settings

    def settings_exist(self) -> bool:
        return (
            self.session.query(AppSettings.id).filter_by(id=_SINGLETON_ID).first()
            is not None
        )

    def update_settings(
        self,
        *,
        system_name: str | None = None,
        bot_url: str | None = None,
        support_line_1: str | None = None,
        support_line_2: str | None = None,
        timezone: str | None = None,
        order_prefix: str | None = None,
        api_docs_url: str | None = None,
        commit: bool = True,
    ) -> AppSettings:
        settings = self.get_settings(commit=commit)
        updates: dict[str, str] = {}
        if system_name is not None:
            value = system_name.strip()
            if not 1 <= len(value) <= 80:
                raise ValueError("system_name must contain 1-80 characters")
            updates["system_name"] = value
        if bot_url is not None:
            value = bot_url.strip()
            if not _BOT_URL_RE.fullmatch(value):
                raise ValueError("bot_url must be an https://t.me bot URL")
            updates["bot_url"] = value.rstrip("/")
        for name, value in (
            ("support_line_1", support_line_1),
            ("support_line_2", support_line_2),
        ):
            if value is not None:
                value = value.strip()
                if len(value) > 200:
                    raise ValueError(f"{name} must contain at most 200 characters")
                updates[name] = value
        if timezone is not None:
            if not validate_timezone(timezone):
                raise ValueError(f"Invalid IANA timezone: {timezone!r}")
            updates["timezone"] = timezone
        if order_prefix is not None:
            value = order_prefix.strip().upper()
            if not _ORDER_PREFIX_RE.fullmatch(value):
                raise ValueError(
                    "order_prefix must contain 2-8 uppercase letters or digits"
                )
            if value.startswith("TU"):
                raise ValueError("order_prefix cannot start with TU")
            updates["order_prefix"] = value
        if api_docs_url is not None:
            updates["api_docs_url"] = _https_url(
                "api_docs_url", api_docs_url, required=False
            )
        for name, value in updates.items():
            setattr(settings, name, value)
        if commit:
            self.session.commit()
            self.session.refresh(settings)
        else:
            self.session.flush()
        return settings
