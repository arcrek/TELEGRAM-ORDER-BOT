"""
Service layer for Image of the Day (IOTD) settings.
"""

from sqlalchemy.orm import Session

from src.database.models.iotd_settings import IotdSettings


class IotdSettingsService:
    """Service for managing global IOTD settings."""

    _SINGLETON_ID = "global"

    def __init__(self, session: Session):
        self.session = session

    def get_settings(self) -> IotdSettings:
        settings = (
            self.session.query(IotdSettings).filter_by(id=self._SINGLETON_ID).first()
        )
        if settings:
            return settings

        settings = IotdSettings(id=self._SINGLETON_ID, image_url=None)
        self.session.add(settings)
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def get_image_url(self) -> str | None:
        settings = self.get_settings()
        url = settings.image_url.strip() if settings.image_url else None
        return url or None

    def set_image_url(self, image_url: str | None) -> IotdSettings:
        settings = self.get_settings()
        if image_url is None:
            settings.image_url = None
        else:
            trimmed = str(image_url).strip()
            settings.image_url = trimmed or None
        self.session.commit()
        self.session.refresh(settings)
        return settings

