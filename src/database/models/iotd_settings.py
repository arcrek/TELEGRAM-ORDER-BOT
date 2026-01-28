"""
Image-of-the-day (IOTD) settings model.
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from src.database.models.base import Base


class IotdSettings(Base):
    """Singleton-style settings for the Image of the Day feature."""

    __tablename__ = "iotd_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    image_url = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

