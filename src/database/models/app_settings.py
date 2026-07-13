"""
App settings model — singleton row for global application configuration.
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func
from src.database.models.base import Base


class AppSettings(Base):
    """Singleton-style settings row for global app configuration."""

    __tablename__ = "app_settings"

    id = Column(String, primary_key=True)
    system_name = Column(
        String(80),
        nullable=False,
        default="Bot Order System",
        server_default="Bot Order System",
    )
    bot_url = Column(String(255), nullable=False, default="", server_default="")
    support_line_1 = Column(String(200), nullable=False, default="", server_default="")
    support_line_2 = Column(String(200), nullable=False, default="", server_default="")
    # IANA timezone name, e.g. "Asia/Ho_Chi_Minh"
    timezone = Column(String, nullable=False, default="Asia/Ho_Chi_Minh")
    order_prefix = Column(
        String(8), nullable=False, default="ORD", server_default="ORD"
    )
    api_docs_url = Column(String(2048), nullable=False, default="", server_default="")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
