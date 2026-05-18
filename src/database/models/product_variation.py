"""
Product variation model.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models.base import Base


class ProductVariation(Base):
    """Product variation model."""

    __tablename__ = "product_variations"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g., "Pro 12M 1PCS"
    price = Column(Integer, nullable=False)  # Price in VND
    stock = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # Which reward system applies: 'bonus', 'discount', or 'both'
    benefit_mode = Column(String, default='both', nullable=False)
    # Warning threshold for inventory aging / expiry tracking
    warning_threshold_value = Column(Integer, nullable=True)
    warning_threshold_unit = Column(String(10), nullable=True)  # 'days' | 'months' | 'years'
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="variations")
    order_items = relationship("OrderItem", back_populates="variation")
    pre_uploaded_products = relationship("PreUploadedProduct", back_populates="variation")
    bonus_tiers = relationship("BonusTier", back_populates="variation", cascade="all, delete-orphan")
    discount_tiers = relationship("DiscountTier", back_populates="variation", cascade="all, delete-orphan")

