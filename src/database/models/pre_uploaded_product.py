"""
Pre-uploaded product model.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models.base import Base


class PreUploadedProduct(Base):
    """Pre-uploaded product model."""

    __tablename__ = "pre_uploaded_products"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    variation_id = Column(String, ForeignKey("product_variations.id"), nullable=False)
    product_data = Column(Text, nullable=False)  # The actual product data to deliver (JSON)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by_order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="pre_uploaded_products")
    variation = relationship("ProductVariation", back_populates="pre_uploaded_products")
    order = relationship("Order", foreign_keys=[used_by_order_id])

