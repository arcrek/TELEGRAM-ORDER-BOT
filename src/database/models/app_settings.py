"""
App settings model — singleton row for global application configuration.
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from src.database.models.base import Base


class AppSettings(Base):
    """Singleton-style settings row for global app configuration."""

    __tablename__ = "app_settings"

    id = Column(String, primary_key=True)
    # IANA timezone name, e.g. "Asia/Ho_Chi_Minh"
    timezone = Column(String, nullable=False, default="Asia/Ho_Chi_Minh")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
