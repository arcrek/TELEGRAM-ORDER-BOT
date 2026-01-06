"""
Product model.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models.base import Base
from src.database.models.enums import DeliveryType


class Product(Base):
    """Product model."""

    __tablename__ = "products"

    id = Column(String, primary_key=True)  # ProductID
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    delivery_type = Column(Enum(DeliveryType, native_enum=False), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    variations = relationship("ProductVariation", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")
    pre_uploaded_products = relationship("PreUploadedProduct", back_populates="product")
    supplier_assignments = relationship("ProductSupplierAssignment", back_populates="product", cascade="all, delete-orphan")

