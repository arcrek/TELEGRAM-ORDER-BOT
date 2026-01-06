"""
Admin model for dashboard access.
"""
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from src.database.models.base import Base


class AdminRole(str, Enum):
    """Admin role enum."""

    ADMIN = "admin"  # Full access
    VIEWER = "viewer"  # Read-only access


class Admin(Base):
    """Admin model for dashboard access."""

    __tablename__ = "admins"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(SQLEnum(AdminRole, native_enum=False), default=AdminRole.VIEWER, nullable=False)
    language = Column(String, default="en", nullable=False)  # 'en' or 'vi'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)

