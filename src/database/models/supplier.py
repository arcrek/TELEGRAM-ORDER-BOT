"""
Supplier model.
"""
from sqlalchemy import BigInteger, Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.models.base import Base


class Supplier(Base):
    """Supplier model."""

    __tablename__ = "suppliers"

    id = Column(String, primary_key=True)
    telegram_user_id = Column(BigInteger, nullable=False, unique=True)  # Supplier's Telegram user ID
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    supplier_orders = relationship("SupplierOrder", back_populates="supplier")
    product_assignments = relationship("ProductSupplierAssignment", back_populates="supplier", cascade="all, delete-orphan")

