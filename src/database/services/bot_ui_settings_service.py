"""
Service layer for global bot UI settings.
"""
from typing import Optional
from sqlalchemy.orm import Session
from src.database.models.bot_ui_settings import BotUiSettings


class BotUiSettingsService:
    """Service for managing global bot selection prompt settings."""

    _SINGLETON_ID = "global"

    def __init__(self, session: Session):
        self.session = session

    def get_settings(self) -> BotUiSettings:
        settings = (
            self.session.query(BotUiSettings)
            .filter_by(id=self._SINGLETON_ID)
            .first()
        )
        if settings:
            return settings

        settings = BotUiSettings(
            id=self._SINGLETON_ID,
            product_choose_text=None,
            variation_choose_text=None,
        )
        self.session.add(settings)
        self.session.commit()
        self.session.refresh(settings)
        return settings

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = str(value).strip()
        return trimmed or None

    def update_settings(
        self,
        *,
        product_choose_text: Optional[str] = None,
        variation_choose_text: Optional[str] = None,
    ) -> BotUiSettings:
        settings = self.get_settings()
        settings.product_choose_text = self._normalize_text(product_choose_text)
        settings.variation_choose_text = self._normalize_text(variation_choose_text)
        self.session.commit()
        self.session.refresh(settings)
        return settings

