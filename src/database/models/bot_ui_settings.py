"""
Bot UI settings model for configurable selection prompts.
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from src.database.models.base import Base


class BotUiSettings(Base):
    """Singleton-style settings row for bot selection prompt texts."""

    __tablename__ = "bot_ui_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    product_choose_text = Column(Text, nullable=True)
    variation_choose_text = Column(Text, nullable=True)
    webapp_button_text = Column(Text, nullable=True)
    webapp_url = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
